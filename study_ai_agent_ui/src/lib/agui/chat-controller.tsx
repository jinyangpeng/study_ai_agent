/**
 * 自定义 Chat Controller
 *
 * 用 :func:`useExternalStoreRuntime` 把 AG-UI 后端、Session 本地状态、
 * 消息渲染（assistant-ui）三端粘合起来。
 *
 * 关键能力：
 *   - 状态完全受 React 控制（messages 来自 SessionContext）
 *   - 多会话：每个 session 对应一个 threadId + 一份消息快照
 *   - 切换 session / 新建 session 都会重新挂载 runtime 的 messages
 *   - 取消、重新生成等操作都通过 ref 暴露给上层组件
 *
 * 关键设计：每条 assistant message 拥有自己的 AG-UI state
 *   - 老的实现把 STATE_SNAPSHOT 写进全局 AguiStateContext，由右侧
 *     StatePanel 渲染 → 切会话 / 多轮时会"老 plan 串到新回答"的副作用；
 *   - 现在的实现把 state 写到 message 的 ``metadata.custom.state`` 上：
 *       - 流式阶段：``onStateSnapshot`` 回调把每次快照 patch 到 streaming
 *         placeholder 的 metadata；
 *       - 完成阶段：placeholder 与 final 消息 **共用同一个 id**，把
 *         ``metadata.custom.state`` 一起带过去，UI 直接读 message 自带
 *         state 渲染 plan / review / code_changes / citations。
 *   - 副作用：每条消息独立 state，渲染组件也无须走 Context。
 *
 * 设计要点：
 *   - 内部 executeRun 用 ref 包装的稳定回调，不会让 adapter 随每次 render 重建
 *   - adapter 的 useMemo 依赖最小化：只依赖 messages + isRunning
 *   - 切换 session 时清空流式状态；持久化消息更新不会触发 abort
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  useExternalStoreRuntime,
  type AppendMessage,
  type TextMessagePart,
  type ThreadMessageLike,
  type ToolCallMessagePart,
} from '@assistant-ui/react';
import type {
  ExternalStoreAdapter,
  ThreadMessage,
} from '@assistant-ui/react';
import type { ReadonlyJSONValue } from 'assistant-stream/utils';

import { useConfig, useSession, useSkill, useAguiState } from '@/context';
import { runAguiAgent, runResultToContent } from './run';
import type { AguiMessage, AguiStateSnapshot } from './events';

type AssistantMessageContent = TextMessagePart | ToolCallMessagePart;

function extractTextFromContent(
  content: ThreadMessageLike['content'],
): string {
  if (typeof content === 'string') return content;
  return content
    .filter((p): p is TextMessagePart => p.type === 'text')
    .map((p) => p.text)
    .join('');
}

function extractText(append: AppendMessage): string {
  if (append.content && append.content.length > 0) {
    return append.content
      .filter((p) => p.type === 'text')
      .map((p) => (p.type === 'text' ? p.text : ''))
      .join('');
  }
  return '';
}

function genId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID();
  }
  return `m-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function makeUserMessage(text: string): ThreadMessageLike {
  return {
    id: genId(),
    role: 'user',
    content: text,
    createdAt: new Date(),
  };
}

function makeStreamingAssistant(usedIds?: Set<string>): ThreadMessageLike {
  let id = genId();
  if (usedIds) {
    while (usedIds.has(id)) {
      id = genId();
    }
    usedIds.add(id);
  }
  return {
    id,
    role: 'assistant',
    content: '',
    createdAt: new Date(),
    status: { type: 'running' },
  };
}

function messagesToAguiHistory(messages: ThreadMessageLike[]): AguiMessage[] {
  const usedIds = new Set<string>();
  return messages
    .filter((m) => m.role === 'user' || m.role === 'assistant' || m.role === 'system')
    .map((m) => {
      let id = m.id;
      if (!id) {
        do {
          id = genId();
        } while (usedIds.has(id));
      }
      usedIds.add(id);
      return {
        id,
        role: m.role as AguiMessage['role'],
        content: extractTextFromContent(m.content),
      };
    });
}

function buildAssistantContent(
  rawContent: ReturnType<typeof runResultToContent>,
): AssistantMessageContent[] {
  return rawContent.map((c) => {
    if (c.type === 'text') {
      return { type: 'text', text: c.text } satisfies TextMessagePart;
    }
    return {
      type: 'tool-call',
      toolCallId: c.toolCallId,
      toolName: c.toolName,
      args: c.args,
      argsText: c.argsText,
      // run.ts 已经把 result 归一化成 string（含 ''），这里原样透传。
      // 不再做 "c.result !== undefined" 的条件 spread —— 否则后端
      // 返回空结果时 part 会一直停在 running，UI 永远显示 "等待中"。
      result: c.result as ReadonlyJSONValue | undefined,
    } satisfies ToolCallMessagePart;
  });
}

/**
 * 把 ThreadMessageLike 转换为 assistant-ui 内部的 ThreadMessage
 *
 * ExternalStoreAdapter 的 ``convertMessage`` 需要这个映射。
 *
 * 关键：即使上游传来 id 缺失的脏数据，也要保证这里返回的 ThreadMessage.id
 * 全局唯一。assistant-ui 内部会以 id 为主键去重，重复 id 会抛
 * "A message with the same id already exists in the parent tree"。
 */
function toThreadMessage(m: ThreadMessageLike, idx: number): ThreadMessage {
  const custom: Record<string, unknown> = {};
  if (m.metadata?.custom && typeof m.metadata.custom === 'object') {
    Object.assign(custom, m.metadata.custom);
  }
  const fallbackId = `tmp-${idx}-${Math.random().toString(36).slice(2, 8)}`;
  return {
    id: m.id ?? fallbackId,
    role: m.role,
    content:
      typeof m.content === 'string'
        ? m.content
        : (m.content as AssistantMessageContent[]),
    createdAt: m.createdAt ?? new Date(),
    // status 只对 assistant 消息有意义；user/system 消息不要传 status 字段
    ...(m.role === 'assistant' || m.status
      ? { status: m.status ?? { type: 'complete' as const, reason: 'unknown' as const } }
      : {}),
    ...(m.attachments ? { attachments: [...m.attachments] } : {}),
    metadata: {
      custom,
      ...(m.metadata?.unstable_state !== undefined
        ? { unstable_state: m.metadata.unstable_state as ReadonlyJSONValue }
        : {}),
    },
  } as ThreadMessage;
}

export interface UseChatControllerOptions {
  /** 当 run 出现错误时调用 */
  onError?: (err: Error) => void;
  /** 调试日志 */
  onDebug?: (event: string, data?: unknown) => void;
}

export function useChatController(opts: UseChatControllerOptions = {}) {
  const { config } = useConfig();
  const session = useSession();
  const skillCtx = useSkill();
  const { setCurrentStage } = useAguiState();

  // 流式临时消息（assistant 占位 + 增量文本）
  const [streamingMessages, setStreamingMessages] = useState<ThreadMessageLike[]>([]);
  const [isRunning, setIsRunning] = useState(false);

  const activeId = session.activeId;
  const persistedMessages = session.currentMessages;

  // 持久化 + 流式 合并的视图
  // 关键：进入 runtime 前必须保证每条消息都有唯一 id，
  // 防止 assistant-ui 抛 "A message with the same id already exists"。
  // 这里做：1) 缺失 id 的消息补一个；2) 按 id 去重，保留首次出现。
  const viewMessages = useMemo<ThreadMessageLike[]>(() => {
    const seen = new Set<string>();
    const out: ThreadMessageLike[] = [];
    const fallback = `m-${Date.now().toString(36)}`;
    for (const m of [...persistedMessages, ...streamingMessages]) {
      if (!m) continue;
      let id = m.id;
      if (!id) {
        id = `${fallback}-${out.length}-${Math.random().toString(36).slice(2, 6)}`;
      }
      if (seen.has(id)) continue;
      seen.add(id);
      out.push({ ...m, id });
    }
    return out;
  }, [persistedMessages, streamingMessages]);

  // 当前 run 的 AbortController
  const abortRef = useRef<AbortController | null>(null);
  // 防止过期 run 回调污染
  const runIdRef = useRef(0);
  // 持久化 opts 到 ref，避免 adapter 重建
  const optsRef = useRef(opts);
  optsRef.current = opts;
  // 持久化 skill / apiBaseUrl 到 ref
  const apiBaseUrlRef = useRef(config.apiBaseUrl);
  apiBaseUrlRef.current = config.apiBaseUrl;
  const skillRef = useRef(skillCtx.currentSkill);
  skillRef.current = skillCtx.currentSkill;

  // 只在切换 session 时清空 streaming。
  // 注意：不要把 persistedMessages 放进依赖，否则 executeRun 写入新消息时
  // 此 effect 会先一步 abort 我们自己发起的请求。
  useEffect(() => {
    setStreamingMessages([]);
    abortRef.current?.abort();
    abortRef.current = null;
    setIsRunning(false);
  }, [activeId]);

  // -------------------------------------------------------------------
  // 内部：执行一次 run
  // -------------------------------------------------------------------
  // 两种模式：
  //   - 'append'      （默认）：把 userMessage 追加到 persistedMessages 后面，重跑
  //   - 'regenerate'           ：重跑最后一条 assistant，但 baseMessages 不动
  //                             （用于 assistant-ui 的 onReload：点"重新生成"覆盖上次结果）
  type RunMode = 'append' | 'regenerate';
  const executeRunRef = useRef<
    (userMessage: ThreadMessageLike, mode?: RunMode) => Promise<void>
  >(async () => {});

  executeRunRef.current = async (userMessage, mode = 'append') => {
    if (!activeId) return;
    const currentRun = ++runIdRef.current;
    setIsRunning(true);

    // 1) 计算 baseMessages：
    //   - 'append'：在尾部追加新的 user message
    //   - 'regenerate'：去掉最后一条 assistant message（如果是），保留最后一条 user message
    let baseMessages: ThreadMessageLike[];
    if (mode === 'regenerate') {
      // 找到最后一条 user / assistant 消息，截断到 user 末尾
      let lastUserIdx = -1;
      for (let i = persistedMessages.length - 1; i >= 0; i--) {
        if (persistedMessages[i].role === 'user') {
          lastUserIdx = i;
          break;
        }
      }
      if (lastUserIdx === -1) return; // 没有 user 消息可重发
      baseMessages = persistedMessages.slice(0, lastUserIdx + 1);
      // 写回 session —— 立刻把"老 assistant"隐藏，避免视觉上叠加两条
      session.setMessages(activeId, baseMessages);
    } else {
      baseMessages = [...persistedMessages, userMessage];
      // 把 user 消息写进 session —— 这样会话标题能立即用首条用户消息生成
      // 同时 streaming 阶段出错时 user 消息也不会丢
      session.setMessages(activeId, baseMessages);
    }

    const history = messagesToAguiHistory(baseMessages);
    const threadId = activeId;
    const skill = skillRef.current;
    const apiBaseUrl = apiBaseUrlRef.current;

    const usedIds = new Set<string>();
    baseMessages.forEach((m) => m.id && usedIds.add(m.id));
    userMessage.id && usedIds.add(userMessage.id);

    const placeholder = makeStreamingAssistant(usedIds);
    setStreamingMessages([placeholder]);

    // 用 ref 缓存最新 state，避免 setStreamingMessages 闭包过期
    const latestStateRef = useRefForRun<AguiStateSnapshot | null>(null);
    const ac = new AbortController();
    abortRef.current = ac;

    // 流式 state 写入：把 placeholder 的 metadata.custom.state 更新到最新
    const writeStateToStreaming = (snapshot: AguiStateSnapshot) => {
      latestStateRef.current = snapshot;
      const safeSnapshot = snapshot;
      setStreamingMessages((prev) =>
        prev.map((m) =>
          m.id === placeholder.id
            ? {
                ...m,
                metadata: {
                  ...(m.metadata ?? {}),
                  custom: {
                    ...((m.metadata && m.metadata.custom) || {}),
                    state: safeSnapshot,
                  },
                },
              }
            : m,
        ),
      );
    };

    try {
      const result = await runAguiAgent({
        apiBaseUrl,
        threadId,
        skill,
        history,
        abortSignal: ac.signal,
        onDebug: optsRef.current.onDebug,
        onStageChange: (stepName) => {
          setCurrentStage(stepName);
        },
        onStateSnapshot: writeStateToStreaming,
      });

      if (currentRun !== runIdRef.current) return;

      const contentParts = buildAssistantContent(runResultToContent(result));

      // placeholder 与 final 消息用同一个 id，metadata 一起带过去
      const finalAssistant: ThreadMessageLike = {
        id: placeholder.id,
        role: 'assistant',
        content: contentParts,
        createdAt: placeholder.createdAt ?? new Date(),
        status: { type: 'complete', reason: 'stop' },
        metadata: {
          ...(placeholder.metadata ?? {}),
          custom: {
            ...((placeholder.metadata && placeholder.metadata.custom) || {}),
            // 优先用 run 返回的 finalState；流式阶段如果没收到（极少见），
            // 回退到 ref 里缓存的最新值
            state: result.finalState ?? latestStateRef.current ?? {},
          },
        },
      };

      session.setMessages(activeId, [...baseMessages, finalAssistant]);
      setStreamingMessages([]);
    } catch (err) {
      if (currentRun !== runIdRef.current) return;
      const error = err instanceof Error ? err : new Error(String(err));
      if (error.name === 'AbortError') {
        // 取消：保留 placeholder 的 metadata（可能携带部分 state），
        // 状态标记为 cancelled
        const partial: ThreadMessageLike = {
          ...placeholder,
          status: { type: 'incomplete', reason: 'cancelled' },
        };
        session.setMessages(activeId, [...baseMessages, partial]);
      } else {
        const errorMsg: ThreadMessageLike = {
          id: genId(),
          role: 'assistant',
          content: [
            {
              type: 'text',
              text: `⚠️ ${error.message}`,
            },
          ],
          createdAt: new Date(),
          status: { type: 'incomplete', reason: 'error' },
        };
        session.setMessages(activeId, [...baseMessages, errorMsg]);
        optsRef.current.onError?.(error);
      }
      setStreamingMessages([]);
    } finally {
      if (currentRun === runIdRef.current) {
        setIsRunning(false);
        abortRef.current = null;
        setCurrentStage(undefined);
      }
    }
  };

  // 暴露给 adapter 的稳定引用
  const executeRun = useCallback((m: ThreadMessageLike) => executeRunRef.current(m), []);

  // -------------------------------------------------------------------
  // ExternalStoreAdapter —— 依赖最小化（只依赖 messages + isRunning）
  // -------------------------------------------------------------------
  const adapter = useMemo<ExternalStoreAdapter<ThreadMessageLike>>(() => {
    return {
      messages: viewMessages,
      isRunning,
      isDisabled: false,
      setMessages: (next) => {
        if (!activeId) return;
        session.setMessages(activeId, next);
      },
      convertMessage: toThreadMessage,
      onNew: async (append: AppendMessage) => {
        const text = extractText(append);
        if (!text) return;
        const userMsg = makeUserMessage(text);
        await executeRun(userMsg);
      },
      onEdit: async (append: AppendMessage) => {
        const text = extractText(append);
        if (!text) return;
        const userMsg = makeUserMessage(text);
        await executeRun(userMsg);
      },
      onReload: async () => {
        // 找到最后一条 user message，重发；本次是"覆盖上次 assistant 结果"
        // 而不是追加新消息 —— mode: 'regenerate' 会先把最后一条 assistant
        // 截掉，再让新结果落到同一个 id 上。
        const lastUser = [...persistedMessages].reverse().find((m) => m.role === 'user');
        if (!lastUser) return;
        await executeRunRef.current(lastUser, 'regenerate');
      },
      onCancel: async () => {
        abortRef.current?.abort();
        setIsRunning(false);
      },
      adapters: {
        threadList: {
          threadId: activeId ?? undefined,
          threads: session.sessions.map((s) => ({
            status: 'regular' as const,
            threadId: s.id,
            title: s.title,
          })),
          onSwitchToNewThread: () => {
            session.createNew(skillCtx.currentSkill);
          },
          onSwitchToThread: (id: string) => {
            session.switchTo(id);
          },
          onDelete: (id: string) => {
            session.remove(id);
          },
          onRename: (id: string, title: string) => {
            session.rename(id, title);
          },
        },
      },
    };
    // 故意省略：activeId、session、executeRun —— 都用 ref / 闭包当前值
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viewMessages, isRunning, skillCtx.currentSkill]);

  const runtime = useExternalStoreRuntime<ThreadMessageLike>(adapter);

  // imperative 控制（暴露给外部）
  const controller = useMemo(
    () => ({
      newChat: () => {
        if (isRunning) {
          abortRef.current?.abort();
        }
        session.createNew(skillCtx.currentSkill);
      },
      deleteCurrent: () => {
        if (activeId) session.remove(activeId);
      },
      renameCurrent: (title: string) => {
        if (activeId) session.rename(activeId, title);
      },
      cancel: () => {
        abortRef.current?.abort();
        setIsRunning(false);
      },
    }),
    [activeId, isRunning, session, skillCtx.currentSkill],
  );

  return { runtime, controller, isRunning, activeId };
}

// ---------------------------------------------------------------------------
// 内部小工具：在一次 run 内部使用的 "受控 ref"
// ---------------------------------------------------------------------------
// 普通 useRef 不行（hook 规则不允许条件调用），所以做成一个普通工厂返回
// { current } 形状的容器；这样可以在 executeRunRef.current 内部随便用。
function useRefForRun<T>(initial: T): { current: T } {
  return { current: initial };
}
