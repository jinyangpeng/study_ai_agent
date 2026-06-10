import { createHttpClient } from '@/lib/api';

export interface HealthInfo {
  status: string;
  agent?: { name?: string };
  /** 协议名（如 "ag-ui"）—— AG-UI 协议已上线即此字段为 "ag-ui" */
  protocol?: string;
  /** 后端的默认 skill id（与 /skeletons 响应里的 default 字段一致） */
  default_skill?: string;
}

/** 健康检查（对应后端 GET /health） */
export async function fetchHealth(
  apiBaseUrl: string,
  signal?: AbortSignal,
): Promise<HealthInfo> {
  const http = createHttpClient(apiBaseUrl);
  return http.get<HealthInfo>('/health', { signal });
}
