/**
 * 会话（Session）Context
 *
 * 提供：
 *   - 当前 session id（也写入 localStorage 用于刷新后恢复）
 *   - 列表 / 切换 / 新建 / 删除 / 重命名
 *   - 消息快照存储（按 session id 分桶）
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
  /** 创建一个新 session（自动激活）并返回新 id */
  createNew: (skillId?: string) => string;
  /** 删除 session（如果删除的是当前，则切到最近一个） */
  remove: (id: string) => void;
  /** 重命名 */
  rename: (id: string, title: string) => void;
  /** 更新消息快照（用于持久化） */
  setMessages: (id: string, messages: ThreadMessageLike[]) => void;
  /** 把当前 session 标记为已活跃（更新 updatedAt） */
  touch: (id: string) => void;
}

const SessionContext = createContext<SessionContextValue | undefined>(undefined);

function genId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID();
  }
  return `s-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
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
    };
  }, [store, switchTo, createNew, remove, rename, setMessages, touch]);

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionContextValue {
  const ctx = useContext(SessionContext);
  if (!ctx) {
    throw new Error('useSession must be used within a SessionProvider');
  }
  return ctx;
}
