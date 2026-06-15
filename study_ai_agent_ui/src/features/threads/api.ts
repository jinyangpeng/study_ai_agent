/**
 * Thread / 会话历史 API 客户端
 *
 * 对应后端 PostgreSQL checkpointer 暴露的 ``/threads`` 路由族，
 * 用于：
 *   - 列出所有历史会话（``fetchThreads``）
 *   - 拉取某会话的完整消息 + state（``fetchThreadState``）
 *   - 删除会话（``deleteThread``）
 *
 * 设计
 * ----
 * 整个前端只有「本地的 SessionStorage（localStorage）」一种会话元数据源，
 * 这个客户端补的是「服务端持久化」这条新链路 —— 当 localStorage 被清空、
 * 跨设备访问、或纯后端跑的 session（如 CLI 测试）时，UI 仍能拿到历史。
 */
import { ApiError, createHttpClient } from '@/lib/api';

import type {
  DeleteThreadResponse,
  ListThreadsResponse,
  ThreadStateResponse,
} from './types';

export async function fetchThreads(
  apiBaseUrl: string,
  opts: { limit?: number; signal?: AbortSignal } = {},
): Promise<ListThreadsResponse> {
  const http = createHttpClient(apiBaseUrl);
  return http.get<ListThreadsResponse>('/threads', {
    query: { limit: opts.limit },
    signal: opts.signal,
  });
}

export async function fetchThreadState(
  apiBaseUrl: string,
  threadId: string,
  opts: { signal?: AbortSignal } = {},
): Promise<ThreadStateResponse | null> {
  const http = createHttpClient(apiBaseUrl);
  try {
    return await http.get<ThreadStateResponse>(
      `/threads/${encodeURIComponent(threadId)}/state`,
      { signal: opts.signal },
    );
  } catch (err) {
    // 404 = 服务端从未写入过这个 thread 的 checkpoint（首次访问新会话时正常）
    if (err instanceof ApiError && err.status === 404) {
      return null;
    }
    throw err;
  }
}

export async function deleteThread(
  apiBaseUrl: string,
  threadId: string,
  opts: { signal?: AbortSignal } = {},
): Promise<DeleteThreadResponse | null> {
  const http = createHttpClient(apiBaseUrl);
  try {
    return await http.delete<DeleteThreadResponse>(
      `/threads/${encodeURIComponent(threadId)}`,
      { signal: opts.signal },
    );
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      return null;
    }
    throw err;
  }
}
