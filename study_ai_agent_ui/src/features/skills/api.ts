/**
 * 智能体发现 API
 *
 * 对应后端 GET /skeletons，用于渲染智能体选择器。
 */
import { http } from '@/lib/http';
import type { SkeletonsResponse } from './types';

/** 拉取所有已注册的智能体 */
export async function fetchSkeletons(
  apiBaseUrl: string,
  signal?: AbortSignal,
): Promise<SkeletonsResponse> {
  const http = createHttpClient(apiBaseUrl);
  return http.get<SkeletonsResponse>('/skeletons', { signal });
}
