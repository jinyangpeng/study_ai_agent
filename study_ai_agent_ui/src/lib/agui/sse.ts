/**
 * AG-UI 协议的 SSE 解析器
 *
 * AG-UI SSE 帧格式（text/event-stream）：
 *   data: {"type":"<TYPE>", ...}\n
 *   \n
 *
 * 注意：AG-UI **不**使用标准 SSE 的 `event:` 字段 —— 类型嵌在 data JSON 的
 * `type` 字段中。所以解析时只需积累 data 行，遇到空行时尝试 JSON.parse
 * data 拿 `type`。
 */
import type { AguiEvent, AguiEventType } from './events';

export interface SseParseHandlers {
  onEvent: (event: AguiEvent) => void;
  /** 非 JSON data 行（罕见，但 SSE 允许 data: foo 这样的原始字符串） */
  onRawData?: (eventType: string, data: string) => void;
}

/**
 * 逐 chunk 解析 SSE 字节流（保持跨行的状态）。
 * 每个 chunk 解码为 utf-8 字符串，缓冲完整的事件帧后回调。
 */
export function createSseParser(handlers: SseParseHandlers): {
  feed: (chunk: string) => void;
  reset: () => void;
} {
  let buffer = '';
  const dataLines: string[] = [];

  const dispatch = () => {
    if (dataLines.length === 0) return;
    const dataStr = dataLines.join('\n');
    dataLines.length = 0;
    if (dataStr.length === 0) return;
    try {
      const parsed = JSON.parse(dataStr) as AguiEvent;
      // AG-UI: type 在 JSON 里；兼容标准 SSE 的 event 字段
      const t = (parsed as { type?: string }).type as AguiEventType | undefined;
      if (t) {
        handlers.onEvent(parsed);
      } else {
        // 没有 type 字段，回退为 raw
        handlers.onRawData?.('message', dataStr);
      }
    } catch {
      handlers.onRawData?.('message', dataStr);
    }
  };

  return {
    feed(chunk: string) {
      buffer += chunk;
      let idx: number;
      // 找完整的 \n 行（处理 \r\n 与 \n）
      while ((idx = buffer.indexOf('\n')) !== -1) {
        const line = buffer.slice(0, idx).replace(/\r$/, '');
        buffer = buffer.slice(idx + 1);
        if (line === '') {
          // 事件帧结束
          dispatch();
        } else if (line.startsWith(':')) {
          // SSE 注释，忽略
          continue;
        } else {
          const colonIdx = line.indexOf(':');
          const field = colonIdx === -1 ? line : line.slice(0, colonIdx);
          const value = colonIdx === -1 ? '' : line.slice(colonIdx + 1).replace(/^ /, '');
          if (field === 'data') {
            dataLines.push(value);
          } else if (field === 'event') {
            // 标准 SSE event 字段 —— 当前 AG-UI 不使用，保留以备扩展
            // 不做处理（type 在 JSON 里）
            void value;
          } else if (field === 'id' || field === 'retry') {
            // 暂不处理 last-event-id / 重试
          }
        }
      }
    },
    reset() {
      buffer = '';
      dataLines.length = 0;
    },
  };
}
