/**
 * Thread / 会话历史 API 类型
 *
 * 对应后端 ``GET /threads`` / ``GET /threads/{thread_id}/state`` /
 * ``DELETE /threads/{thread_id}``。响应体里的 messages 字段使用
 * AG-UI 形状 —— 跟 ``RunAgentInput.messages`` 同构。
 */

export interface ThreadSummary {
  /** AG-UI thread_id，等同于前端的 session id */
  thread_id: string;
  /** 最新 checkpoint 的 UUID */
  checkpoint_id: string;
  /** ISO8601 时间戳 */
  ts: string;
  /** 最新 checkpoint 视角下的消息条数 */
  message_count: number;
  /** 首条 user 消息的纯文本（用于"标题兜底"） */
  first_user_message: string | null;
}

export interface ListThreadsResponse {
  threads: ThreadSummary[];
  count: number;
}

/**
 * AG-UI 形状的 message（与 ``RunAgentInput.messages`` 项同构）。
 * 字段名用 snake_case，与后端 Pydantic ``populate_by_name`` 兼容。
 */
export interface AguiBackendMessage {
  id: string;
  role: 'user' | 'assistant' | 'system' | 'tool';
  content: string;
  /** 仅 ToolMessage 存在 */
  tool_call_id?: string;
  /** 仅 AIMessage 存在（OpenAI 形状） */
  tool_calls?: AguiBackendToolCall[];
  name?: string;
}

export interface AguiBackendToolCall {
  id: string;
  type: 'function';
  function: {
    name: string;
    /** JSON 字符串 */
    arguments: string;
  };
}

export interface ThreadStateResponse {
  thread_id: string;
  checkpoint_id: string;
  ts: string;
  messages: AguiBackendMessage[];
  /** LangGraph state 的其余字段（plan / review / citations / final_answer ...） */
  state: Record<string, unknown>;
}

export interface DeleteThreadResponse {
  deleted: boolean;
  thread_id: string;
}
