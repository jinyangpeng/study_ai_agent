/**
 * Threads（服务端会话历史）功能统一出口
 *
 * 与 ``features/sessions/`` 的区别：
 *   - ``sessions/``   本地元数据 + 消息快照（localStorage，弱一致性）
 *   - ``threads/``    服务端 PostgreSQL checkpointer 视图（强一致、跨设备）
 */
export type {
  AguiBackendMessage,
  AguiBackendToolCall,
  DeleteThreadResponse,
  ListThreadsResponse,
  ThreadStateResponse,
  ThreadSummary,
} from './types';

export { deleteThread, fetchThreadState, fetchThreads } from './api';
