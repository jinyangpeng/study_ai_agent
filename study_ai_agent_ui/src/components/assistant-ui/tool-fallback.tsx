/**
 * 工具调用（tool call）通用 Fallback 渲染
 *
 * assistant-ui 把后端返回的工具调用渲染为 ``ToolCallMessagePart``；
 * 我们的 AG-UI 后端会通过 ``TOOL_CALL_START`` / ``TOOL_CALL_ARGS`` /
 * ``TOOL_CALL_RESULT`` 事件把工具调用推过来，前端 ChatModelAdapter
 * 把它们组装成 ``ToolCallMessagePart``。
 *
 * 这里给出一个简洁的折叠卡片：默认展开、显示工具名 + 参数 + 结果。
 *
 * Props 完全兼容 assistant-ui 的 ``ToolCallMessagePartComponent``。
 */
import { useState } from 'react';
import { ChevronRightIcon, WrenchIcon } from 'lucide-react';
import type { ToolCallMessagePartComponent } from '@assistant-ui/react';

const ToolFallbackImpl: ToolCallMessagePartComponent = ({
  toolName,
  argsText,
  result,
  isError,
}) => {
  const [open, setOpen] = useState(true);
  return (
    <div
      className={
        'border-border bg-muted/30 my-2 flex flex-col rounded-md border text-xs' +
        (isError ? ' border-destructive/50' : '')
      }
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="text-foreground hover:bg-muted/60 flex items-center gap-2 rounded-t-md px-3 py-1.5 text-left transition-colors"
      >
        <ChevronRightIcon
          className={'h-3 w-3 transition-transform' + (open ? ' rotate-90' : '')}
        />
        <WrenchIcon className="h-3 w-3" />
        <span className="font-mono font-medium">{toolName}</span>
        {isError && <span className="text-destructive ml-2">error</span>}
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
          {result !== undefined && result !== null && (
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
