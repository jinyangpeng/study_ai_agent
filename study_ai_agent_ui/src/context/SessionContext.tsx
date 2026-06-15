/**
 * 会话（Session）Context
 *
 * 提供：
 *   - 当前 session id（也写入 localStorage 用于刷新后恢复）
 *     —— **此 id 既是前端会话 id，也是 AG-UI 协议的 ``thread_id``**。
 *        前端点击"新建会话"时即在 :func:`createNew` 中用
 *        :func:`crypto.randomUUID` 现场生成，作为该 session 在所有
 *        AG-UI ``POST /`` 请求里 ``RunAgentInput.thread_id`` 字段的值。
 *        这样后端 PostgreSQL checkpointer 会按这个 id 分桶落盘。
 *   - 列表 / 切换 / 新建 / 删除 / 重命名
 *   - 消息快照存储（按 session id 分桶）
 *   - ``loadFromBackend``：从服务端 checkpointer 拉取历史（与 localStorage
 *     形成冗余 / 跨设备访问支持）
 *
 * 状态形状故意保持简单：把所有 session 元数据 + 消息快照都加载到 React state，
 * 写入防抖（每个 useEffect 触发后写一次 localStorage）。
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import type { ReactNode } from 'react';
import type { ThreadMessageLike } from '@assistant-ui/react';

import { ApiError } from '@/lib/api';
import { fetchThreadState } from '@/features/threads';
import type { AguiBackendMessage, AguiBackendToolCall } from '@/features/threads';
import {
  deriveTitle,
  loadSessions,
  saveSessions,
  type SessionMeta,
  type SessionStorage,
} from '@/features/sessions';

interface SessionContextValue {
  /** 当前激活的 session id（可能为 null = 还没创建） */
  activeId: string | null;
  /** 全部 session 元数据（按 updatedAt 倒序） */
  sessions: SessionMeta[];
  /** 当前 session 的消息快照 */
  currentMessages: ThreadMessageLike[];
  /** 切换到已有 session */
  switchTo: (id: string) => void;
  /**
   * 创建一个新 session（自动激活）并返回新 id。
   * **新 id 即 AG-UI thread_id** —— 用 ``crypto.randomUUID()`` 生成，
   * 保证全局唯一、与后端 checkpointer 的 thread_id 字段对齐。
   */
  createNew: (skillId?: string) => string;
  /** 删除 session（如果删除的是当前，则切到最近一个） */
  remove: (id: string) => void;
  /** 重命名 */
  rename: (id: string, title: string) => void;
  /** 更新消息快照（用于持久化） */
  setMessages: (id: string, messages: ThreadMessageLike[]) => void;
  /** 把当前 session 标记为已活跃（更新 updatedAt） */
  touch: (id: string) => void;
  /**
   * 从后端 checkpointer 拉取 ``threadId`` 的最新消息快照，写入当前 session。
   * 用于：
   *   - 切到旧会话但 localStorage 被清空时，恢复消息
   *   - 跨设备访问同一 thread_id
   * 返回是否成功落库（后端无历史 = 失败、抛错 = 失败）。
   */
  loadFromBackend: (threadId: string, apiBaseUrl: string) => Promise<boolean>;
}

const SessionContext = createContext<SessionContextValue | undefined>(undefined);

function genId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    // 注意：这是**新会话的 AG-UI thread_id** 的生成点。
    // 后端 checkpointer 会按这个 id 在 PostgreSQL 里分桶落盘，
    // 后续 ``POST /`` 的 ``RunAgentInput.thread_id`` 字段也传这个值。
    return crypto.randomUUID();
  }
  return `s-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

// ---------------------------------------------------------------------------
// 后端 AG-UI message → assistant-ui ThreadMessageLike 转换
// ---------------------------------------------------------------------------
// 服务端 ``GET /threads/{id}/state`` 返回的 message 形状和前端已有的
// ``AguiMessage`` 一致（id / role / content / name / tool_call_id）。
// assistant-ui 的 ``ThreadMessageLike`` 额外支持把 tool_calls 渲染成
// ``ToolCallMessagePart`` —— 这里把 OpenAI 形状的 tool_calls 转过去。
function toolCallArgsText(args: string): string {
  // 已经是合法 JSON 字符串就直接用；否则原样塞进 argsText 兜底显示
  try {
    JSON.parse(args);
    return args;
  } catch {
    return args;
  }
}

function aguiBackendToThreadMessage(
  m: AguiBackendMessage,
  idx: number,
): ThreadMessageLike {
  // 工具消息：ThreadMessageLike 不支持 'tool' role，
  // 且前端 ``messagesToAguiHistory`` 本来就过滤掉 tool 角色，
  // 所以这里直接并入下一条 assistant 消息的 tool_calls 块即可；
  // 但当前实现是 1:1 映射，最简单的处理是丢掉 tool 消息。
  // （assistant-ui 渲染 tool_calls 用 ``ToolCallMessagePart``，tool
  // 消息的作用只是把结果回填到那个 part；后端目前没回填 result，所以
  // 即便丢掉也至少不会渲染异常。）
  if (m.role === 'tool') {
    // 兜底：把 tool 结果以 user 消息渲染，保留信息供回看
    return {
      id: m.id || `m-${idx}`,
      role: 'user',
      content: `[tool ${m.tool_call_id ?? ''}] ${
        typeof m.content === 'string' ? m.content : JSON.stringify(m.content ?? '')
      }`.trim(),
      createdAt: new Date(),
    };
  }

  // assistant：把 tool_calls 渲染成 ToolCallMessagePart
  if (m.role === 'assistant' && m.tool_calls && m.tool_calls.length > 0) {
    const parts = m.tool_calls.map((tc: AguiBackendToolCall) => ({
      type: 'tool-call' as const,
      toolCallId: tc.id,
      toolName: tc.function.name,
      args: (() => {
        try {
          return JSON.parse(tc.function.arguments);
        } catch {
          return {};
        }
      })(),
      argsText: toolCallArgsText(tc.function.arguments),
      result: undefined,
    }));
    return {
      id: m.id || `m-${idx}`,
      role: 'assistant',
      content: parts,
      createdAt: new Date(),
      status: { type: 'complete', reason: 'stop' },
    };
  }

  // user / system / 纯文本 assistant
  return {
    id: m.id || `m-${idx}`,
    role: m.role as 'user' | 'assistant' | 'system',
    content: m.content,
    createdAt: new Date(),
    ...(m.role === 'assistant'
      ? { status: { type: 'complete' as const, reason: 'unknown' as const } }
      : {}),
  };
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const [store, setStore] = useState<SessionStorage>(() => loadSessions());
  const storeRef = useRef(store);
  storeRef.current = store;

  // 持久化（每次 store 变化后写一次）
  useEffect(() => {
    saveSessions(store);
  }, [store]);

  const switchTo = useCallback((id: string) => {
    setStore((prev) => {
      if (!prev.sessions.some((s) => s.id === id)) return prev;
      return { ...prev, activeId: id };
    });
  }, []);

  const createNew = useCallback((skillId?: string): string => {
    const id = genId();
    const now = Date.now();
    setStore((prev) => {
      const meta: SessionMeta = {
        id,
        title: '新会话',
        createdAt: now,
        updatedAt: now,
        skillId,
        messageCount: 0,
      };
      return {
        ...prev,
        sessions: [meta, ...prev.sessions],
        messages: { ...prev.messages, [id]: [] },
        activeId: id,
      };
    });
    return id;
  }, []);

  const remove = useCallback((id: string) => {
    setStore((prev) => {
      const sessions = prev.sessions.filter((s) => s.id !== id);
      const { [id]: _removed, ...rest } = prev.messages;
      void _removed;
      let activeId = prev.activeId;
      if (activeId === id) {
        activeId = sessions[0]?.id ?? null;
      }
      return { ...prev, sessions, messages: rest, activeId };
    });
  }, []);

  const rename = useCallback((id: string, title: string) => {
    setStore((prev) => ({
      ...prev,
      sessions: prev.sessions.map((s) =>
        s.id === id ? { ...s, title: title.trim() || s.title } : s,
      ),
    }));
  }, []);

  const setMessages = useCallback(
    (id: string, messages: ThreadMessageLike[]) => {
      setStore((prev) => {
        if (!(id in prev.messages) && !prev.sessions.some((s) => s.id === id)) return prev;
        const nextMessages = { ...prev.messages, [id]: messages };
        const title = deriveTitle(messages);
        const messageCount = messages.length;
        const now = Date.now();
        const sessions = prev.sessions.map((s) => {
          if (s.id !== id) return s;
          // 1) 标题：仅在还是"新会话"或空时更新（避免覆盖用户手动重命名）
          // 2) 但如果消息数变 0（清空），重置为"新会话"
          const nextTitle = messageCount === 0
            ? '新会话'
            : s.title === '新会话' || s.title === ''
              ? title
              : s.title;
          return { ...s, title: nextTitle, messageCount, updatedAt: now };
        });
        return { ...prev, messages: nextMessages, sessions };
      });
    },
    [],
  );

  const touch = useCallback((id: string) => {
    setStore((prev) => {
      if (!prev.sessions.some((s) => s.id === id)) return prev;
      return {
        ...prev,
        sessions: prev.sessions.map((s) =>
          s.id === id ? { ...s, updatedAt: Date.now() } : s,
        ),
      };
    });
  }, []);

  /**
   * 从后端 checkpointer 拉取 ``threadId`` 的最新消息快照，写入当前 session。
   *
   * 成功条件：后端有 messages 且 network / 鉴权无错。
   * 失败（404 = 后端无该 thread、网络异常）一律 ``return false``，调用方
   * 可据此决定是否回退到 localStorage 缓存。
   */
  const loadFromBackend = useCallback(
    async (threadId: string, apiBaseUrl: string): Promise<boolean> => {
      try {
        const state = await fetchThreadState(apiBaseUrl, threadId);
        if (!state || !Array.isArray(state.messages) || state.messages.length === 0) {
          return false;
        }
        const restored = state.messages.map((m, i) => aguiBackendToThreadMessage(m, i));
        setStore((prev) => {
          // 仅当 id 在 store 中（避免给已删的 session 复活）才落地
          if (!prev.sessions.some((s) => s.id === threadId)) return prev;
          const title = deriveTitle(restored);
          const messageCount = restored.length;
          const sessions = prev.sessions.map((s) =>
            s.id === threadId
              ? {
                  ...s,
                  title:
                    messageCount === 0
                      ? '新会话'
                      : s.title === '新会话' || s.title === ''
                        ? title
                        : s.title,
                  messageCount,
                  updatedAt: Date.now(),
                }
              : s,
          );
          return {
            ...prev,
            messages: { ...prev.messages, [threadId]: restored },
            sessions,
          };
        });
        return true;
      } catch (err) {
        if (err instanceof ApiError) {
          console.warn(
            `[SessionContext] loadFromBackend failed: HTTP ${err.status} ${err.message}`,
          );
        } else {
          console.warn('[SessionContext] loadFromBackend error:', err);
        }
        return false;
      }
    },
    [],
  );

  const value = useMemo<SessionContextValue>(() => {
    const currentMessages = store.activeId ? store.messages[store.activeId] ?? [] : [];
    return {
      activeId: store.activeId,
      sessions: store.sessions,
      currentMessages,
      switchTo,
      createNew,
      remove,
      rename,
      setMessages,
      touch,
      loadFromBackend,
    };
  }, [store, switchTo, createNew, remove, rename, setMessages, touch, loadFromBackend]);

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionContextValue {
  const ctx = useContext(SessionContext);
  if (!ctx) {
    throw new Error('useSession must be used within a SessionProvider');
  }
  return ctx;
}
