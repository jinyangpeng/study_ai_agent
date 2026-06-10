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
 * 设计要点：
 *   - 内部 executeRun 用 useEvent（ref 包装的稳定回调），不会让 adapter
 *     随每次 render 重建
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

import { useConfig, useSession, useSkill } from '@/context';
import { runAguiAgent, runResultToContent } from './run';
import type { AguiMessage } from './events';

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

function makeStreamingAssistant(): ThreadMessageLike {
  return {
    id: genId(),
    role: 'assistant',
    content: '',
    createdAt: new Date(),
    status: { type: 'running' },
  };
}

function messagesToAguiHistory(messages: ThreadMessageLike[]): AguiMessage[] {
  return messages
    .filter((m) => m.role === 'user' || m.role === 'assistant' || m.role === 'system')
    .map((m) => ({
      id: m.id ?? genId(),
      role: m.role as AguiMessage['role'],
      content: extractTextFromContent(m.content),
    }));
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
      ...(c.result !== undefined ? { result: c.result } : {}),
    } satisfies ToolCallMessagePart;
  });
}

/**
 * 把 ThreadMessageLike 转换为 assistant-ui 内部的 ThreadMessage
 *
 * ExternalStoreAdapter 的 ``convertMessage`` 需要这个映射。
 */
function toThreadMessage(m: ThreadMessageLike, idx: number): ThreadMessage {
  const custom: Record<string, unknown> = {};
  if (m.metadata?.custom && typeof m.metadata.custom === 'object') {
    Object.assign(custom, m.metadata.custom);
  }
  return {
    id: m.id ?? `tmp-${idx}`,
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
  /** 当 run 结束时调用的回调（例如刷新 StatePanel） */
  onState?: (snapshot: unknown) => void;
  /** 当 run 出现错误时调用 */
  onError?: (err: Error) => void;
  /** 调试日志 */
  onDebug?: (event: string, data?: unknown) => void;
}

export function useChatController(opts: UseChatControllerOptions = {}) {
  const { config } = useConfig();
  const session = useSession();
  const skillCtx = useSkill();

  // 流式临时消息（assistant 占位 + 增量文本）
  const [streamingMessages, setStreamingMessages] = useState<ThreadMessageLike[]>([]);
  const [isRunning, setIsRunning] = useState(false);

  const activeId = session.activeId;
  const persistedMessages = session.currentMessages;

  // 持久化 + 流式 合并的视图
  const viewMessages = useMemo<ThreadMessageLike[]>(
    () => [...persistedMessages, ...streamingMessages],
    [persistedMessages, streamingMessages],
  );

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
  const executeRunRef = useRef<
    (userMessage: ThreadMessageLike) => Promise<void>
  >(async () => {});

  executeRunRef.current = async (userMessage: ThreadMessageLike) => {
    if (!activeId) return;
    const currentRun = ++runIdRef.current;
    setIsRunning(true);

    const history = messagesToAguiHistory([...persistedMessages, userMessage]);
    const threadId = activeId;
    const skill = skillRef.current;
    const apiBaseUrl = apiBaseUrlRef.current;

    // 临时占位
    const placeholder = makeStreamingAssistant();
    setStreamingMessages([placeholder]);

    const ac = new AbortController();
    abortRef.current = ac;

    try {
      const result = await runAguiAgent({
        apiBaseUrl,
        threadId,
        skill,
        history,
        abortSignal: ac.signal,
        onDebug: optsRef.current.onDebug,
      });

      if (currentRun !== runIdRef.current) return;

      if (result.finalState) {
        optsRef.current.onState?.(result.finalState);
      }

      const contentParts = buildAssistantContent(runResultToContent(result));

      const finalAssistant: ThreadMessageLike = {
        id: genId(),
        role: 'assistant',
        content: contentParts,
        createdAt: new Date(),
        status: { type: 'complete', reason: 'stop' },
      };

      // 落盘：持久化消息 + 这次的 user + assistant
      // 注意：此时 persistedMessages 来自闭包，session.setMessages
      // 会更新全局 store，本组件下次 render 时会拿到新值
      session.setMessages(activeId, [...persistedMessages, userMessage, finalAssistant]);
      setStreamingMessages([]);
    } catch (err) {
      if (currentRun !== runIdRef.current) return;
      const error = err instanceof Error ? err : new Error(String(err));
      if (error.name === 'AbortError') {
        // 取消：保留已生成的部分
        const partial: ThreadMessageLike = {
          ...placeholder,
          status: { type: 'incomplete', reason: 'cancelled' },
        };
        session.setMessages(activeId, [...persistedMessages, userMessage, partial]);
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
        session.setMessages(activeId, [...persistedMessages, userMessage, errorMsg]);
        optsRef.current.onError?.(error);
      }
      setStreamingMessages([]);
    } finally {
      if (currentRun === runIdRef.current) {
        setIsRunning(false);
        abortRef.current = null;
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
        // 找到最后一条 user message，重发
        const lastUser = [...persistedMessages].reverse().find((m) => m.role === 'user');
        if (!lastUser) return;
        await executeRun(lastUser);
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
