/**
 * 统一 fetch 客户端
 *
 * - 自动拼接 baseURL（绝对地址直接使用，相对地址走 vite 代理）
 * - 统一 JSON 解析
 * - 统一错误格式：抛出带 status / message 的 ApiError
 * - 支持 AbortSignal
 */

export class ApiError extends Error {
  readonly status: number;
  readonly detail?: unknown;

  constructor(message: string, status: number, detail?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

export interface RequestOptions extends Omit<globalThis.RequestInit, 'body' | 'signal'> {
  body?: unknown;
  /** 额外的 query 参数 */
  query?: Record<string, string | number | boolean | undefined>;
  signal?: AbortSignal;
}

function buildUrl(baseURL: string, path: string, query?: RequestOptions['query']): string {
  // path 已经是绝对 http(s) 时直接使用；否则与 baseURL 拼接
  const fullUrl = /^https?:\/\//i.test(path) ? path : `${baseURL.replace(/\/+$/, '')}/${path.replace(/^\/+/, '')}`;

  if (!query) return fullUrl;

  const params = new URLSearchParams();
  Object.entries(query).forEach(([k, v]) => {
    if (v !== undefined && v !== null) params.append(k, String(v));
  });
  const qs = params.toString();
  return qs ? `${fullUrl}?${qs}` : fullUrl;
}

export interface HttpClient {
  request<T = unknown>(path: string, options?: RequestOptions): Promise<T>;
  get<T = unknown>(path: string, options?: RequestOptions): Promise<T>;
  post<T = unknown>(path: string, body?: unknown, options?: RequestOptions): Promise<T>;
  delete<T = unknown>(path: string, options?: RequestOptions): Promise<T>;
}

export function createHttpClient(baseURL: string): HttpClient {
  async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const { body, query, headers, signal, ...rest } = options;
    const url = buildUrl(baseURL, path, query);

    const init: globalThis.RequestInit = {
      ...rest,
      headers: {
        'Content-Type': 'application/json',
        ...headers,
      },
      signal,
    };

    if (body !== undefined) {
      init.body = typeof body === 'string' ? body : JSON.stringify(body);
    }

    let response: Response;
    try {
      response = await fetch(url, init);
    } catch (err) {
      // 网络层错误（断网、CORS、abort）
      if ((err as Error).name === 'AbortError') {
        throw err;
      }
      throw new ApiError(`网络请求失败: ${(err as Error).message}`, 0);
    }

    if (!response.ok) {
      let detail: unknown = undefined;
      let message = `HTTP ${response.status} ${response.statusText}`;
      try {
        detail = await response.json();
        if (detail && typeof detail === 'object' && 'detail' in detail) {
          const d = (detail as { detail: unknown }).detail;
          message = typeof d === 'string' ? d : JSON.stringify(d);
        }
      } catch {
        // 响应不是 JSON，忽略
      }
      throw new ApiError(message, response.status, detail);
    }

    // 204 / 空响应
    if (response.status === 204) {
      return undefined as T;
    }

    const contentType = response.headers.get('content-type') ?? '';
    if (contentType.includes('application/json')) {
      return (await response.json()) as T;
    }
    return (await response.text()) as unknown as T;
  }

  return {
    request,
    get: (path, options) => request(path, { ...options, method: 'GET' }),
    post: (path, body, options) => request(path, { ...options, method: 'POST', body }),
    delete: (path, options) => request(path, { ...options, method: 'DELETE' }),
  };
}
