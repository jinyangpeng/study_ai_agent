/** 配置的 localStorage 持久化 */
import type { AppConfig } from '@/types';

const STORAGE_KEY = 'study-ai-agent:config';

export const DEFAULT_CONFIG: AppConfig = {
  apiBaseUrl: 'http://localhost:8000',
  defaultSkill: 'default',
};

export function loadConfig(): AppConfig {
  if (typeof window === 'undefined') return { ...DEFAULT_CONFIG };
  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) return { ...DEFAULT_CONFIG };
  try {
    const parsed = JSON.parse(raw) as Partial<AppConfig>;
    // 白名单 pick：丢弃已废弃字段（如旧的 mockMode），避免脏数据渗透
    return {
      apiBaseUrl: typeof parsed.apiBaseUrl === 'string' ? parsed.apiBaseUrl : DEFAULT_CONFIG.apiBaseUrl,
      defaultSkill: typeof parsed.defaultSkill === 'string' ? parsed.defaultSkill : DEFAULT_CONFIG.defaultSkill,
    };
  } catch {
    return { ...DEFAULT_CONFIG };
  }
}

export function saveConfig(config: AppConfig): void {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
}

export function clearConfig(): void {
  if (typeof window === 'undefined') return;
  window.localStorage.removeItem(STORAGE_KEY);
}
