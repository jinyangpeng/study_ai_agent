/**
 * 会话持久化（localStorage）
 *
 * 存储结构：
 *   - ``sessions``: 元数据数组（按 updatedAt 倒序）
 *   - ``messages``: 消息快照按 id 存，避免元数据过大
 *   - ``activeId``: 上次激活的 session id
 *
 * 读取失败/版本不匹配时整体丢弃并返回空数据，避免脏数据导致 crash。
 */
import type { ThreadMessageLike } from '@assistant-ui/react';

import type { SessionMeta, SessionStorage } from './types';

const STORAGE_KEY = 'study-ai-agent:sessions';
const STORAGE_VERSION = 1;

const EMPTY: SessionStorage = {
  version: STORAGE_VERSION,
  sessions: [],
  messages: {},
  activeId: null,
};

function safeParse(raw: string | null): SessionStorage {
  if (!raw) return clone(EMPTY);
  try {
    const parsed = JSON.parse(raw) as Partial<SessionStorage>;
    if (!parsed || typeof parsed !== 'object') return clone(EMPTY);
    if (parsed.version !== STORAGE_VERSION) return clone(EMPTY);
    return {
      version: STORAGE_VERSION,
      sessions: Array.isArray(parsed.sessions) ? (parsed.sessions as SessionMeta[]) : [],
      messages:
        parsed.messages && typeof parsed.messages === 'object'
          ? (parsed.messages as Record<string, ThreadMessageLike[]>)
          : {},
      activeId: typeof parsed.activeId === 'string' ? parsed.activeId : null,
    };
  } catch {
    return clone(EMPTY);
  }
}

function clone<T>(v: T): T {
  return JSON.parse(JSON.stringify(v)) as T;
}

export function loadSessions(): SessionStorage {
  if (typeof window === 'undefined') return clone(EMPTY);
  return safeParse(window.localStorage.getItem(STORAGE_KEY));
}

export function saveSessions(data: SessionStorage): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
  } catch {
    // 超出配额等情况静默忽略
  }
}

export function clearSessions(): void {
  if (typeof window === 'undefined') return;
  window.localStorage.removeItem(STORAGE_KEY);
}

/** 用首条用户消息的内容做标题（截断） */
export function deriveTitle(messages: ThreadMessageLike[]): string {
  const firstUser = messages.find((m) => m.role === 'user');
  const raw =
    typeof firstUser?.content === 'string'
      ? firstUser.content
      : (firstUser?.content
          ?.map((p) => (p.type === 'text' ? p.text : ''))
          .join('') ?? '');
  const trimmed = raw.trim().replace(/\s+/g, ' ');
  if (!trimmed) return '新会话';
  return trimmed.length > 30 ? trimmed.slice(0, 30) + '…' : trimmed;
}

export { EMPTY as EMPTY_SESSION_STORAGE, STORAGE_KEY, STORAGE_VERSION };
