/**
 * AG-UI 协议事件类型（前端镜像）
 *
 * 后端对应模块：``ag_ui.core.types``（Pydantic 模型）。
 * 这里只声明前端关心的子集；新增事件时按需扩展。
 *
 * 协议参考：https://docs.ag-ui.com/concepts/events
 */

export type AguiEventType =
  | 'RUN_STARTED'
  | 'RUN_FINISHED'
  | 'RUN_ERROR'
  | 'TEXT_MESSAGE_START'
  | 'TEXT_MESSAGE_CONTENT'
  | 'TEXT_MESSAGE_END'
  | 'TOOL_CALL_START'
  | 'TOOL_CALL_ARGS'
  | 'TOOL_CALL_END'
  | 'TOOL_CALL_RESULT'
  | 'TOOL_CALL_CHUNK'
  | 'STATE_SNAPSHOT'
  | 'STATE_DELTA'
  | 'MESSAGES_SNAPSHOT'
  | 'STEP_STARTED'
  | 'STEP_FINISHED';

/** 基础事件形状：每个事件都带 ``type`` 字段 */
export interface AguiBaseEvent {
  type: AguiEventType;
  [key: string]: unknown;
}

// ---- run lifecycle ---------------------------------------------------

export interface RunStartedEvent extends AguiBaseEvent {
  type: 'RUN_STARTED';
  thread_id: string;
  run_id: string;
}

export interface RunFinishedEvent extends AguiBaseEvent {
  type: 'RUN_FINISHED';
  thread_id: string;
  run_id: string;
  result?: unknown;
}

export interface RunErrorEvent extends AguiBaseEvent {
  type: 'RUN_ERROR';
  message: string;
  code?: string;
}

// ---- text message -----------------------------------------------------

export interface TextMessageStartEvent extends AguiBaseEvent {
  type: 'TEXT_MESSAGE_START';
  message_id: string;
  role: 'assistant' | 'user' | 'system';
}

export interface TextMessageContentEvent extends AguiBaseEvent {
  type: 'TEXT_MESSAGE_CONTENT';
  message_id: string;
  delta: string;
}

export interface TextMessageEndEvent extends AguiBaseEvent {
  type: 'TEXT_MESSAGE_END';
  message_id: string;
}

// ---- tool call --------------------------------------------------------

export interface ToolCallStartEvent extends AguiBaseEvent {
  type: 'TOOL_CALL_START';
  tool_call_id: string;
  tool_call_name: string;
  parent_message_id?: string;
}

export interface ToolCallArgsEvent extends AguiBaseEvent {
  type: 'TOOL_CALL_ARGS';
  tool_call_id: string;
  delta: string;
}

export interface ToolCallEndEvent extends AguiBaseEvent {
  type: 'TOOL_CALL_END';
  tool_call_id: string;
}

export interface ToolCallResultEvent extends AguiBaseEvent {
  type: 'TOOL_CALL_RESULT';
  message_id: string;
  tool_call_id: string;
  content: string;
  role?: 'tool';
}

export interface ToolCallChunkEvent extends AguiBaseEvent {
  type: 'TOOL_CALL_CHUNK';
  tool_call_id: string;
  tool_call_name?: string;
  delta?: string;
  parent_message_id?: string;
}

// ---- state ------------------------------------------------------------

export interface StateSnapshotEvent extends AguiBaseEvent {
  type: 'STATE_SNAPSHOT';
  snapshot: Record<string, unknown>;
}

export interface StateDeltaEvent extends AguiBaseEvent {
  type: 'STATE_DELTA';
  /** JSON Patch 数组 */
  delta: unknown[];
}

export interface MessagesSnapshotEvent extends AguiBaseEvent {
  type: 'MESSAGES_SNAPSHOT';
  messages: unknown[];
}

// ---- step -------------------------------------------------------------

export interface StepStartedEvent extends AguiBaseEvent {
  type: 'STEP_STARTED';
  step_name: string;
}

export interface StepFinishedEvent extends AguiBaseEvent {
  type: 'STEP_FINISHED';
  step_name: string;
}

// ---- union ------------------------------------------------------------

export type AguiEvent =
  | RunStartedEvent
  | RunFinishedEvent
  | RunErrorEvent
  | TextMessageStartEvent
  | TextMessageContentEvent
  | TextMessageEndEvent
  | ToolCallStartEvent
  | ToolCallArgsEvent
  | ToolCallEndEvent
  | ToolCallResultEvent
  | ToolCallChunkEvent
  | StateSnapshotEvent
  | StateDeltaEvent
  | MessagesSnapshotEvent
  | StepStartedEvent
  | StepFinishedEvent;

// ---- request body (RunAgentInput) -------------------------------------

export interface AguiMessage {
  id: string;
  role: 'user' | 'assistant' | 'system' | 'tool';
  content: string;
  name?: string;
  tool_call_id?: string;
}

export interface AguiTool {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
}

export interface AguiContext {
  description: string;
  value: string;
}

export interface RunAgentInput {
  thread_id: string;
  run_id: string;
  state: Record<string, unknown>;
  messages: AguiMessage[];
  tools: AguiTool[];
  context: AguiContext[];
  forwarded_props: Record<string, unknown>;
}

// ---- aggregated state shapes (for Plan / Review / etc.) ---------------

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

/** 后端 state（来自 STATE_SNAPSHOT）会包含这些字段之一或多个 */
export interface AguiStateSnapshot {
  plan?: PlanShape;
  review?: ReviewShape;
  citations?: CitationShape[];
  code_changes?: CodeChangeShape[];
  final_answer?: string;
  [key: string]: unknown;
}
