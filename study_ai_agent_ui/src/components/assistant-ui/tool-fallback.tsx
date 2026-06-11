/**
 * 工具调用（tool call）通用 Fallback 渲染
 *
 * assistant-ui 把后端返回的工具调用渲染为 ``ToolCallMessagePart``；
 * 我们的 AG-UI 后端会通过 ``TOOL_CALL_START`` / ``TOOL_CALL_ARGS`` /
 * ``TOOL_CALL_RESULT`` 事件把工具调用推过来，前端 ChatModelAdapter
 * 把它们组装成 ``ToolCallMessagePart``。
 *
 * 这里给出一个简洁的折叠卡片：默认展开、显示工具名 + 参数 + 结果。
 * 工具"调用中"（result 还没回来）时显示 Loader 提示。
 *
 * Props 完全兼容 assistant-ui 的 ``ToolCallMessagePartComponent``。
 */
import { useState } from 'react';
import { ChevronRightIcon, Loader2, WrenchIcon } from 'lucide-react';
import type { ToolCallMessagePartComponent } from '@assistant-ui/react';

import { cn } from '@/lib/utils';

const ToolFallbackImpl: ToolCallMessagePartComponent = ({
  toolName,
  argsText,
  result,
  isError,
  status,
}) => {
  const [open, setOpen] = useState(true);

  // ---- 状态判定 --------------------------------------------------------
  // 三种状态：
  //   1) isRunning：part 还在 running / requires-action，且没拿到 result
  //   2) isEmptyDone：执行已结束（complete / incomplete），但 result 为空串/null
  //   3) hasResult：result 有内容，正常渲染
  //
  // 注意：早期版本这里写的是
  //   `result === undefined && result === null`
  // 是恒 false 的死代码（一个值不可能同时 === undefined 和 === null），
  // 导致 isRunning 永远 false，状态徽标 "调用中…" 永远不显示。
  const hasResult = result !== undefined && result !== null && result !== '';
  const partStillRunning = status?.type === 'running' || status?.type === 'requires-action';

  const isRunning = partStillRunning && !hasResult && !isError;
  const isEmptyDone =
    !isError && !hasResult && !partStillRunning;

  return (
    <div
      className={cn(
        'border-border bg-muted/30 my-2 flex flex-col rounded-md border text-xs',
        isError && 'border-destructive/50',
        isRunning && 'border-primary/30',
      )}
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className={cn(
          'text-foreground hover:bg-muted/60 flex items-center gap-2 rounded-t-md px-3 py-1.5 text-left transition-colors',
        )}
      >
        <ChevronRightIcon
          className={cn('h-3 w-3 transition-transform', open && 'rotate-90')}
        />
        <WrenchIcon className="h-3 w-3" />
        <span className="font-mono font-medium">{toolName}</span>

        {/* 状态徽标 —— 优先级：error > running > done */}
        {isError ? (
          <span
            className="bg-destructive/10 text-destructive ml-2 inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[10px] font-medium"
            data-testid="tool-status-error"
          >
            调用失败
          </span>
        ) : isRunning ? (
          <span
            className="bg-primary/10 text-primary ml-2 inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[10px] font-medium"
            data-testid="tool-status-running"
          >
            <Loader2 className="h-2.5 w-2.5 animate-spin" />
            调用中…
          </span>
        ) : null}
      </button>

      {open && (
        <div className="space-y-2 px-3 pb-2.5">
          {argsText && (
            <div>
              <div className="text-muted-foreground mb-1 font-mono text-[10px] tracking-wider uppercase">
                args
              </div>
              <pre className="border-border bg-background overflow-x-auto rounded border px-2 py-1.5 text-xs">
                <code className="font-mono whitespace-pre">{prettifyJson(argsText)}</code>
              </pre>
            </div>
          )}

          {/* 优先级：error 展示错误 result > running 展示 loader > 空结果展示提示 > 正常 result */}
          {isError ? (
            <div>
              <div className="text-muted-foreground mb-1 font-mono text-[10px] tracking-wider uppercase">
                result
              </div>
              <pre className="border-destructive/30 bg-destructive/5 text-destructive/90 max-h-60 overflow-x-auto rounded border px-2 py-1.5 text-xs">
                <code className="font-mono whitespace-pre">
                  {formatResult(result ?? '(工具返回错误，无详细 result)')}
                </code>
              </pre>
            </div>
          ) : isRunning ? (
            <div>
              <div className="text-muted-foreground mb-1 font-mono text-[10px] tracking-wider uppercase">
                result
              </div>
              <div
                className="border-border bg-background text-muted-foreground flex items-center gap-2 rounded border px-2 py-2 text-xs"
                data-testid="tool-pending-result"
              >
                <Loader2 className="text-primary h-3 w-3 animate-spin" />
                <span>等待工具返回结果…</span>
                <span
                  className="ml-auto font-mono text-[10px] tracking-wider uppercase opacity-60"
                  aria-hidden="true"
                >
                  {status?.type === 'requires-action' ? 'requires-action' : 'running'}
                </span>
              </div>
            </div>
          ) : isEmptyDone ? (
            <div>
              <div className="text-muted-foreground mb-1 font-mono text-[10px] tracking-wider uppercase">
                result
              </div>
              <div
                className="border-border bg-background text-muted-foreground rounded border px-2 py-1.5 text-xs italic"
                data-testid="tool-empty-result"
              >
                （工具执行完成，但未返回内容）
              </div>
            </div>
          ) : (
            <div>
              <div className="text-muted-foreground mb-1 font-mono text-[10px] tracking-wider uppercase">
                result
              </div>
              <pre className="border-border bg-background max-h-60 overflow-x-auto rounded border px-2 py-1.5 text-xs">
                <code className="font-mono whitespace-pre">{formatResult(result)}</code>
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

function prettifyJson(raw: string): string {
  try {
    return JSON.stringify(JSON.parse(raw), null, 2);
  } catch {
    return raw;
  }
}

function formatResult(result: unknown): string {
  if (typeof result === 'string') return result;
  try {
    return JSON.stringify(result, null, 2);
  } catch {
    return String(result);
  }
}

export const ToolFallback = ToolFallbackImpl;
