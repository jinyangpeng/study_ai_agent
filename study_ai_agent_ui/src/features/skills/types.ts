/**
 * 智能体（Skill）相关类型
 *
 * 对应后端 GET /skeletons 的响应形状（src/core/server.py）
 */

/** 单条快捷提示卡（后端 quick_prompts 数组元素） */
export interface QuickPrompt {
  /** lucide-react 图标名（字符串，前端按名映射到组件） */
  icon: string;
  /** 卡片标题 */
  title: string;
  /** 卡片说明（一行） */
  description: string;
  /** 实际发送给后端的 prompt 文本 */
  prompt: string;
}

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
  /** 前端欢迎区个性化快捷提示（由 skill 自身声明） */
  quick_prompts: QuickPrompt[];
}

/** GET /skeletons 响应 */
export interface SkeletonsResponse {
  /** 后端当前默认的 skill id */
  default: string;
  skeletons: Skeleton[];
}
