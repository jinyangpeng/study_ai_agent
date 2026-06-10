/**
 * AG-UI 模块对外类型
 */
import type { AguiStateSnapshot } from './events';
export type { AguiStateSnapshot };

export interface AguiAdapterOptions {
  apiBaseUrl: string;
  getSkill: () => string;
  getThreadId: () => string;
  onState?: (snapshot: AguiStateSnapshot) => void;
  onDebug?: (event: string, data?: unknown) => void;
}
