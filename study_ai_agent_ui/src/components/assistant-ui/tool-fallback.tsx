/**
 * 工具调用（tool call）通用 Fallback 渲染
 *
 * 设计原则
 * --------
 * - 工具调用是 AI 在"做事"，用户需要看到**发生了哪些工具调用 + 大致结果**，
 *   但不需要在每条消息里都看到完整的 args / result JSON（会冲淡正文阅读）。
 * - 渲染策略：
 *     1. 默认展示一行 chip：工具名 + 状态徽标（运行中 / 失败 / 成功）+ 一句话
 *        result 预览（截断到 80 字符）。
 *     2. 点击 chip 展开完整 args / result 详情，方便调试。
 *
 * Props 完全兼容 assistant-ui 的 ``ToolCallMessagePartComponent``。
 */
import { useState } from 'react';
import {
  CheckCircle2,
  ChevronRightIcon,
  Loader2,
  WrenchIcon,
  XCircle,
} from 'lucide-react';
import type { ToolCallMessagePartComponent } from '@assistant-ui/react';

import { cn } from '@/lib/utils';

const RESULT_PREVIEW_LIMIT = 80;

const ToolFallbackImpl: ToolCallMessagePartComponent = ({
  toolName,
  argsText,
  result,
  isError,
  status,
}) => {
  // 默认收起；运行中自动展开 —— 让用户能看到"工具正在跑"
  const [open, setOpen] = useState(false);

  // 状态判定
  // 注意：早期版本写的是 `result === undefined && result === null`
  // （恒 false 死代码），导致 isRunning 永远 false。
  const hasResult = result !== undefined && result !== null && result !== '';
  const partStillRunning =
    status?.type === 'running' || status?.type === 'requires-action';

  const isRunning = partStillRunning && !hasResult && !isError;
  const isEmptyDone = !isError && !hasResult && !partStillRunning;
  // running 时强制展开
  const expanded = open || isRunning;

  const resultText = hasResult
    ? typeof result === 'string'
      ? result
      : safeStringify(result)
    : '';
  const resultPreview = resultText
    ? resultText.replace(/\s+/g, ' ').slice(0, RESULT_PREVIEW_LIMIT) +
      (resultText.length > RESULT_PREVIEW_LIMIT ? '…' : '')
    : '';

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
          'text-foreground hover:bg-muted/60 flex items-center gap-2 rounded-md px-2.5 py-1.5 text-left transition-colors',
        )}
        aria-expanded={expanded}
      >
        <ChevronRightIcon
          className={cn(
            'h-3 w-3 shrink-0 transition-transform',
            expanded && 'rotate-90',
          )}
        />
        <WrenchIcon className="text-muted-foreground h-3 w-3 shrink-0" />
        <span className="font-mono font-medium">{toolName}</span>

        {/* 状态徽标 —— 优先级：error > running > done */}
        {isError ? (
          <span className="bg-destructive/10 text-destructive ml-1 inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[10px] font-medium">
            <XCircle className="h-2.5 w-2.5" />
            调用失败
          </span>
        ) : isRunning ? (
          <span className="bg-primary/10 text-primary ml-1 inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[10px] font-medium">
            <Loader2 className="h-2.5 w-2.5 animate-spin" />
            调用中…
          </span>
        ) : isEmptyDone ? (
          <span className="text-muted-foreground ml-1 rounded-full bg-background px-1.5 py-0.5 text-[10px]">
            无返回值
          </span>
        ) : (
          <span className="ml-1 inline-flex items-center gap-1 rounded-full bg-green-100 px-1.5 py-0.5 text-[10px] font-medium text-green-700 dark:bg-green-900/40 dark:text-green-300">
            <CheckCircle2 className="h-2.5 w-2.5" />
            完成
          </span>
        )}

        {/* 一行 result 预览 —— 让用户在不展开的情况下也能瞥到结论 */}
        {resultPreview && !isError && !isRunning && (
          <span className="text-muted-foreground ml-1 flex-1 truncate text-[11px]">
            {resultPreview}
          </span>
        )}
      </button>

      {expanded && (
        <div className="space-y-2 border-t px-2.5 pb-2.5 pt-2">
          {argsText && (
            <div>
              <div className="text-muted-foreground mb-1 font-mono text-[10px] tracking-wider uppercase">
                args
              </div>
              <pre className="border-border bg-background overflow-x-auto rounded border px-2 py-1.5 text-xs">
                <code className="font-mono whitespace-pre">
                  {prettifyJson(argsText)}
                </code>
              </pre>
            </div>
          )}

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
                <code className="font-mono whitespace-pre">
                  {formatResult(result)}
                </code>
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

function safeStringify(value: unknown): string {
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
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
