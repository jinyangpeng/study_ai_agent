/**
 * 会话（Session）类型定义
 *
 * 一个 session = 一个对话线程，等同于 AG-UI 协议里的 ``thread_id``。
 * 前端用 localStorage 持久化元数据 + 消息快照。
 */
import type { ThreadMessageLike } from '@assistant-ui/react';

export interface SessionMeta {
  /** 唯一 id（UUID），对应 AG-UI thread_id */
  id: string;
  /** 用户可读标题（默认取首条用户消息的前 N 个字符） */
  title: string;
  /** 创建时间（毫秒） */
  createdAt: number;
  /** 最后活跃时间（毫秒） */
  updatedAt: number;
  /** 创建时使用的 skill id（仅展示用，不影响后端路由） */
  skillId?: string;
  /** 消息条数（用于列表展示） */
  messageCount: number;
  /**
   * 是否已向后端发起过至少一次 run。
   *
   * 用于"切到本地无快照的旧会话时是否去后端 checkpointer 拉历史"：
   *   - 从未跑过 → 后端必然 404（dogfood ISSUE-003），跳过
   *   - 跑过但本地为空 → 才走 loadFromBackend
   */
  hasRun?: boolean;
}

export interface SessionRecord extends SessionMeta {
  /** 该会话的完整消息快照（assistant-ui ThreadMessageLike） */
  messages: ThreadMessageLike[];
}

export interface SessionStorage {
  version: number;
  sessions: SessionMeta[];
  /** 消息快照按 session id 单独存储，避免主列表过大 */
  messages: Record<string, ThreadMessageLike[]>;
  /** 当前激活的 session id（页面刷新后还原） */
  activeId: string | null;
}
