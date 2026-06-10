/**
 * 全局共享类型
 *
 * - 仅保留实际业务用到的类型
 * - ChatMessage / ChatStreamEvent 等已由 assistant-ui 内部类型覆盖，不再重复定义
 */

/** 用户在 /config 页面维护的运行时配置 */
export interface AppConfig {
  /** 后端 API 基础地址 */
  apiBaseUrl: string;
  /** 模拟模式：开启后不连接真实后端 */
  mockMode: boolean;
  /** 默认智能体（skill）id，初始化时使用 */
  defaultSkill: string;
}

/** AG-UI 协议事件（来自后端 STATE_SNAPSHOT）的状态形状 */
export interface CitationShape {
  url: string;
  title?: string;
  excerpt?: string;
  accessed_at?: string;
}

export interface CodeChangeShape {
  file: string;
  diff?: string;
  description?: string;
}

export interface PlanStep {
  id: string;
  description: string;
  expected_output?: string;
}

export interface PlanShape {
  goal: string;
  steps: PlanStep[];
  rationale?: string;
}

export interface ReviewShape {
  verdict: 'approve' | 'revise';
  issues: string[];
  suggestions: string[];
}
