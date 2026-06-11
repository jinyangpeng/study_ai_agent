/**
 * 简易错误 Toast
 *
 * 设计目标：流式对话中遇到错误时（onError 回调触发），
 * 在聊天区顶部弹出一个简洁的提示条，包含：
 *   - 友好的错误标题（区分网络/超时/服务端错误）
 *   - 错误详细信息（可折叠）
 *   - 重试 / 关闭 按钮
 *   - 几秒后自动消失
 *
 * 不引入 sonner / radix-toast 等额外依赖，保持轻量。
 */
import { useEffect, useState } from 'react';
import { AlertCircle, ChevronDown, ChevronUp, RefreshCw, X } from 'lucide-react';

import { Button } from '@/components/assistant-ui/ui/button';
import { cn } from '@/lib/utils';

export interface ErrorToastProps {
  /** 错误对象（null/undefined 时不显示） */
  error: Error | null;
  /** 用户点击关闭 */
  onDismiss: () => void;
  /** 用户点击重试 —— 调用方负责重新发起请求 */
  onRetry?: () => void;
  /** 自动消失的延迟（ms）；0 表示不自动消失。默认 8000 */
  autoDismissMs?: number;
  className?: string;
}

/**
 * 把错误归类成 4 类用户友好标题：
 *   - network:    网络层问题（fetch / SSE 流中断）
 *   - timeout:    超时
 *   - server:     4xx / 5xx HTTP 状态
 *   - cancelled:  用户主动取消
 *   - unknown:    兜底
 */
function classifyError(err: Error): { title: string; hint: string } {
  const msg = (err.message || '').toLowerCase();
  if (err.name === 'AbortError' || /aborted|cancel/i.test(msg)) {
    return { title: '已取消', hint: '当前请求被手动停止。' };
  }
  if (/timeout|timed out/.test(msg)) {
    return { title: '请求超时', hint: '后端响应太慢，可以稍后重试或换个模型试试。' };
  }
  if (/failed to fetch|networkerror|network error|sse 流读取失败/.test(msg)) {
    return { title: '网络异常', hint: '请检查后端服务是否启动、网络是否畅通。' };
  }
  if (/\b(4\d\d|5\d\d)\b/.test(msg) || /ag-?ui 后端错误/.test(msg)) {
    return { title: '后端返回错误', hint: '后端服务返回了非 2xx 响应，请查看具体信息。' };
  }
  return { title: '出错了', hint: '发生未知异常，可重试或查看浏览器控制台。' };
}

export function ErrorToast({
  error,
  onDismiss,
  onRetry,
  autoDismissMs = 8000,
  className,
}: ErrorToastProps) {
  const [expanded, setExpanded] = useState(false);

  // 错误变化时重置折叠
  useEffect(() => {
    setExpanded(false);
  }, [error]);

  // 自动消失
  useEffect(() => {
    if (!error || autoDismissMs <= 0) return;
    const id = window.setTimeout(() => {
      onDismiss();
    }, autoDismissMs);
    return () => window.clearTimeout(id);
  }, [error, autoDismissMs, onDismiss]);

  if (!error) return null;

  const { title, hint } = classifyError(error);

  return (
    <div
      role="alert"
      aria-live="assertive"
      data-testid="chat-error-toast"
      className={cn(
        'border-destructive/40 bg-destructive/5 text-destructive',
        'mx-auto mb-2 flex w-full max-w-2xl flex-col gap-2 rounded-lg border px-3 py-2 text-xs shadow-sm',
        'animate-in fade-in slide-in-from-top-2 duration-200',
        className,
      )}
    >
      <div className="flex items-center gap-2">
        <AlertCircle className="h-4 w-4 shrink-0" />
        <span className="font-semibold">{title}</span>
        <span className="text-muted-foreground truncate">· {hint}</span>
        <div className="ml-auto flex items-center gap-1">
          {onRetry && (
            <Button
              size="sm"
              variant="ghost"
              onClick={onRetry}
              title="重试"
              className="h-6 px-2 text-[11px]"
            >
              <RefreshCw className="h-3 w-3" />
              <span>重试</span>
            </Button>
          )}
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            title={expanded ? '收起详情' : '展开详情'}
            className="hover:bg-destructive/10 inline-flex h-6 w-6 items-center justify-center rounded transition-colors"
          >
            {expanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
          </button>
          <button
            type="button"
            onClick={onDismiss}
            title="关闭"
            className="hover:bg-destructive/10 inline-flex h-6 w-6 items-center justify-center rounded transition-colors"
          >
            <X className="h-3 w-3" />
          </button>
        </div>
      </div>

      {expanded && (
        <pre className="border-destructive/20 bg-background text-destructive/90 max-h-40 overflow-auto rounded border px-2 py-1.5 font-mono text-[11px] whitespace-pre-wrap break-all">
          {error.message}
        </pre>
      )}
    </div>
  );
}
