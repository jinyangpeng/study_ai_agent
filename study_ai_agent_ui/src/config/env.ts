/**
 * 构建期/启动期环境配置
 *
 * - 通过 import.meta.env 读取 Vite 注入的变量
 * - 提供默认值，避免运行时 undefined
 */

function readString(key: string, fallback = ''): string {
  const value = import.meta.env[key];
  return typeof value === 'string' && value.length > 0 ? value : fallback;
}

function readNumber(key: string, fallback: number): number {
  const value = import.meta.env[key];
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

export interface EnvConfig {
  /** 应用标题 */
  appTitle: string;
  /** 开发服务器端口 */
  port: number;
  /** 开发服务器主机 */
  host: string;
  /** 后端 API 基础地址（同时作为健康检查与 /api/chat 的 baseURL） */
  apiBaseUrl: string;
  /** 健康检查地址 */
  healthCheckUrl: string;
  /** 是否为开发环境 */
  isDev: boolean;
  /** 是否为生产环境 */
  isProd: boolean;
}

export const env: EnvConfig = {
  appTitle: readString('VITE_APP_TITLE', 'Study AI Agent'),
  port: readNumber('VITE_PORT', 3000),
  host: readString('VITE_HOST', 'localhost'),
  apiBaseUrl: readString('VITE_API_BASE_URL', 'http://localhost:8000'),
  healthCheckUrl: readString('VITE_HEALTH_CHECK_URL', 'http://localhost:8000/health'),
  isDev: import.meta.env.DEV,
  isProd: import.meta.env.PROD,
};

/** 打印当前环境配置（仅开发环境） */
export function printEnvConfig(): void {
  if (!env.isDev) return;
  // eslint-disable-next-line no-console
  console.group('%c🔧 环境配置', 'color: #6366f1; font-weight: bold;');
  // eslint-disable-next-line no-console
  console.log('应用标题:', env.appTitle);
  // eslint-disable-next-line no-console
  console.log('API 地址:', env.apiBaseUrl);
  // eslint-disable-next-line no-console
  console.log('健康检查:', env.healthCheckUrl);
  // eslint-disable-next-line no-console
  console.log('运行环境:', env.isDev ? '开发' : '生产');
  // eslint-disable-next-line no-console
  console.groupEnd();
}
