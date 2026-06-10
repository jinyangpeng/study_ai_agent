/**
 * 智能体（Skill）相关类型
 *
 * 对应后端 GET /skeletons 的响应形状（src/core/server.py）
 */

/** 后端 SkillModule 的前端镜像 */
export interface Skeleton {
  /** 智能体 id，与后端 SkillModule.id 一致（如 "coding" / "research"） */
  id: string;
  /** 中文展示名（如 "编程 Agent"） */
  name: string;
  /** 一句话描述 */
  description: string;
  /** 工具数量（只用于列表展示） */
  tool_count: number;
  /** HITL 工具规则：{ tool_name: { allowed_decisions: string[] } } */
  hitl_rules: Record<string, { allowed_decisions: string[] }>;
}

/** GET /skeletons 响应 */
export interface SkeletonsResponse {
  /** 后端当前默认的 skill id */
  default: string;
  skeletons: Skeleton[];
}
