/**
 * 执行一次 AG-UI ``run`` 并返回聚合结果
 *
 * 这是一个**纯函数**，不依赖 React。可以被：
 *   - 旧的 :func:`createAguiAdapter` 用（ChatModelAdapter 适配器）
 *   - 新的 :func:`useChatController` 用（ExternalStoreAdapter 适配器）
 *
 * 设计目标：把 SSE / 事件聚合逻辑抽出来，让上层只关心"发什么 + 怎么用结果"。
 */
import type { ReadonlyJSONObject, ReadonlyJSONValue } from 'assistant-stream/utils';

import type {
  AguiEvent,
  AguiMessage,
  AguiStateSnapshot,
  RunAgentInput,
  StateSnapshotEvent,
  TextMessageContentEvent,
  TextMessageEndEvent,
  TextMessageStartEvent,
  ToolCallArgsEvent,
  ToolCallEndEvent,
  ToolCallResultEvent,
  ToolCallStartEvent,
} from './events';
import { createSseParser } from './sse';

export interface AguiRunInput {
  apiBaseUrl: string;
  threadId: string;
  skill: string;
  /** 整条对话历史（不包含即将发出去的那条；这条会作为最后一条 user 消息一起发送） */
  history: AguiMessage[];
  abortSignal?: AbortSignal;
  onDebug?: (event: string, data?: unknown) => void;
  /** 流式回调：每个 TEXT_MESSAGE_CONTENT 都会触发一次（增量） */
  onTextDelta?: (messageId: string, delta: string) => void;
  /** 每个工具调用增量 */
  onToolCallDelta?: (toolCallId: string, delta: string) => void;
  /**
   * 阶段切换回调 —— STEP_STARTED 时触发，stepName 为新阶段；
   * STEP_FINISHED 时 stepName 为 undefined。
   * 用于在 Composer banner 中显示"当前正在做 X"。
   */
  onStageChange?: (stepName: string | undefined) => void;
  /**
   * STATE_SNAPSHOT 事件触发，传入最新 state 快照（覆盖式）。
   * 典型用途：把 state 实时绑到 streaming message 的 metadata 上，
   * 这样 UI 可以按"每条消息一份 state"的维度渲染，无需走全局 context。
   */
  onStateSnapshot?: (snapshot: AguiStateSnapshot) => void;
}

export interface AguiTextBlock {
  messageId: string;
  role: 'assistant' | 'user' | 'system';
  text: string;
}

export interface AguiToolCall {
  toolCallId: string;
  name: string;
  argsText: string;
  result?: string;
}

export interface AguiRunResult {
  texts: AguiTextBlock[];
  toolCalls: AguiToolCall[];
  finalState: AguiStateSnapshot | null;
}

/**
 * 执行一次 AG-UI 流式 run，聚合返回结果。
 *
 * 流式逻辑：
 *   - 在 onTextDelta / onToolCallDelta 中实时推送增量
 *   - 最后返回聚合并的 texts / toolCalls / finalState
 */
export async function runAguiAgent(input: AguiRunInput): Promise<AguiRunResult> {
  const { apiBaseUrl, threadId, skill, history, abortSignal, onDebug } = input;
  const runId =
    typeof crypto !== 'undefined' && 'randomUUID' in crypto
      ? crypto.randomUUID()
      : `run-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

  const body: RunAgentInput = {
    thread_id: threadId,
    run_id: runId,
    state: {},
    messages: history,
    tools: [],
    context: [],
    forwarded_props: { skill },
  };

  const url = `${apiBaseUrl.replace(/\/+$/, '')}/`;
  onDebug?.('request', { url, threadId, skill, messageCount: history.length });

  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    },
    body: JSON.stringify(body),
    signal: abortSignal,
  });

  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`AG-UI 后端错误 ${res.status}: ${text || res.statusText}`);
  }
  if (!res.body) {
    throw new Error('AG-UI 后端未返回流式响应体');
  }

  const textBuffers = new Map<string, { role: AguiTextBlock['role']; text: string }>();
  const toolBuffers = new Map<string, { name: string; args: string; result?: string }>();
  let finalState: AguiStateSnapshot | null = null;

  const usedMessageIds = new Set<string>();
  history.forEach((m) => usedMessageIds.add(m.id));

  const messageIdMap = new Map<string, string>();

  function getSafeMessageId(originalId: string): string {
    if (messageIdMap.has(originalId)) {
      return messageIdMap.get(originalId)!;
    }
    let newId = originalId;
    while (usedMessageIds.has(newId)) {
      newId = `${originalId}-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
    }
    usedMessageIds.add(newId);
    messageIdMap.set(originalId, newId);
    return newId;
  }

  const parser = createSseParser({
    onEvent: (event: AguiEvent) => {
      onDebug?.('event', event);
      switch (event.type) {
        case 'TEXT_MESSAGE_START': {
          const e = event as TextMessageStartEvent;
          const safeId = getSafeMessageId(e.message_id);
          textBuffers.set(safeId, { role: e.role, text: '' });
          break;
        }
        case 'TEXT_MESSAGE_CONTENT': {
          const e = event as TextMessageContentEvent;
          const safeId = getSafeMessageId(e.message_id);
          const buf = textBuffers.get(safeId);
          if (buf) {
            buf.text += e.delta;
            input.onTextDelta?.(e.message_id, e.delta);
          }
          break;
        }
        case 'TEXT_MESSAGE_END': {
          void (event as TextMessageEndEvent);
          break;
        }
        case 'TOOL_CALL_START': {
          const e = event as ToolCallStartEvent;
          toolBuffers.set(e.tool_call_id, { name: e.tool_call_name, args: '' });
          break;
        }
        case 'TOOL_CALL_ARGS': {
          const e = event as ToolCallArgsEvent;
          const buf = toolBuffers.get(e.tool_call_id);
          if (buf) {
            buf.args += e.delta;
            input.onToolCallDelta?.(e.tool_call_id, e.delta);
          }
          break;
        }
        case 'TOOL_CALL_END': {
          void (event as ToolCallEndEvent);
          break;
        }
        case 'TOOL_CALL_RESULT': {
          const e = event as ToolCallResultEvent;
          const buf = toolBuffers.get(e.tool_call_id);
          if (buf) buf.result = e.content;
          break;
        }
        case 'STATE_SNAPSHOT': {
          const e = event as StateSnapshotEvent;
          finalState = e.snapshot as AguiStateSnapshot;
          // 实时把 state 推给调用方；不阻塞解析，调用方用 ref 收集即可
          input.onStateSnapshot?.(finalState);
          break;
        }
        case 'STEP_STARTED': {
          const e = event as Extract<AguiEvent, { type: 'STEP_STARTED' }>;
          input.onStageChange?.(e.step_name);
          break;
        }
        case 'STEP_FINISHED': {
          input.onStageChange?.(undefined);
          break;
        }
        case 'RUN_ERROR': {
          const e = event as Extract<AguiEvent, { type: 'RUN_ERROR' }>;
          throw new Error(`AG-UI run 错误：${e.message}${e.code ? ` (${e.code})` : ''}`);
        }
        default:
          break;
      }
    },
  });

  const reader = res.body.getReader();
  const decoder = new TextDecoder('utf-8');
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      parser.feed(decoder.decode(value, { stream: true }));
    }
    parser.feed(decoder.decode());
  } catch (err) {
    const e = err as Error;
    if (e.name === 'AbortError') {
      onDebug?.('aborted');
    } else {
      onDebug?.('stream_error', { name: e.name, message: e.message });
      // 包装错误，附加更多上下文
      const wrapped = new Error(
        `SSE 流读取失败 (${e.name}): ${e.message || 'network error'}`,
      );
      (wrapped as Error & { cause?: unknown }).cause = err;
      throw wrapped;
    }
  }

  const texts: AguiTextBlock[] = [];
  for (const [messageId, buf] of textBuffers) {
    texts.push({ messageId, role: buf.role, text: buf.text });
  }

  const toolCalls: AguiToolCall[] = [];
  for (const [toolCallId, buf] of toolBuffers) {
    toolCalls.push({
      toolCallId,
      name: buf.name,
      argsText: buf.args,
      // 始终输出 result 字段（缺省视为空串 ''）——
      // 之前用条件 spread 不写 result，assistant-ui 会把 part 状态锁在
      // 'running' / 'requires-action'，UI 上就永远停在"等待工具返回结果…"。
      // 这里强制设值，让 part 能正常进入 'complete'，空结果由前端另外提示。
      result: buf.result ?? '',
    });
  }

  return { texts, toolCalls, finalState };
}

// ---------------------------------------------------------------------------
// 兼容旧 adapter 的工具函数（保持向后兼容）
// ---------------------------------------------------------------------------

function isJsonObject(v: unknown): v is ReadonlyJSONObject {
  return typeof v === 'object' && v !== null && !Array.isArray(v);
}

/** 把 AguiRunResult 转换为 assistant-ui 的 content 数组 */
export function runResultToContent(
  result: AguiRunResult,
): Array<{ type: 'text'; text: string } | {
  type: 'tool-call';
  toolCallId: string;
  toolName: string;
  args: ReadonlyJSONObject;
  argsText: string;
  result?: unknown;
}> {
  const content: Array<
    | { type: 'text'; text: string }
    | {
        type: 'tool-call';
        toolCallId: string;
        toolName: string;
        args: ReadonlyJSONObject;
        argsText: string;
        result?: unknown;
      }
  > = [];
  for (const t of result.texts) {
    if (!t.text) continue;
    content.push({ type: 'text', text: t.text });
  }
  for (const tc of result.toolCalls) {
    let argsObj: ReadonlyJSONObject = {};
    if (tc.argsText) {
      try {
        const parsed = JSON.parse(tc.argsText);
        if (isJsonObject(parsed)) argsObj = parsed;
      } catch {
        // ignore
      }
    }
    content.push({
      type: 'tool-call',
      toolCallId: tc.toolCallId,
      toolName: tc.name,
      args: argsObj,
      argsText: tc.argsText,
      ...(tc.result !== undefined ? { result: tc.result as ReadonlyJSONValue } : {}),
    });
  }
  return content;
}
