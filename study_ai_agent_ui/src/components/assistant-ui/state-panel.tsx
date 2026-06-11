/**
 * AG-UI 状态面板
 *
 * 渲染后端 ``STATE_SNAPSHOT`` 推送的 plan / review / citations / code_changes /
 * final_answer 等字段。位于聊天区右侧，可关闭。
 *
 * 设计目标：
 *   - 不参与 assistant-ui 渲染树，完全独立
 *   - 通过 :func:`useAguiState` 拿到最新 state
 *   - 字段为空时折叠不显示，避免噪音
 *   - 首次出现内容时自动展开（提升"状态可见性"），用户主动关掉后不再自动开
 *   - 展开/收起带 transition 动画，宽度变化丝滑
 */
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { CheckCircle2, FileText, ListChecks, Quote, Wrench, X, type LucideIcon } from 'lucide-react';

import { useAguiState } from '@/context';
import type { CitationShape, CodeChangeShape, PlanShape, ReviewShape } from '@/lib/agui';
import { Button } from '@/components/assistant-ui';
import { cn } from '@/lib/utils';

export interface StatePanelProps {
  className?: string;
  /** 默认是否展开。默认 false —— 大多数时候不打扰用户 */
  defaultOpen?: boolean;
}

export function StatePanel({ className, defaultOpen = false }: StatePanelProps) {
  const [open, setOpen] = useState(defaultOpen);
  /** 标记用户是否"主动关过"，用于避免再次自动展开骚扰用户 */
  const userDismissedRef = useRef<boolean>(false);
  const { state, resetState } = useAguiState();

  // 计算"是否有任何内容"
  const hasContent =
    Boolean(state.plan) ||
    Boolean(state.review) ||
    (state.citations && state.citations.length > 0) ||
    (state.code_changes && state.code_changes.length > 0) ||
    Boolean(state.final_answer);

  // 首次出现内容（hasContent 从 false → true）时自动展开
  // 触发条件：
  //   - !userDismissedRef.current  用户没有主动关过
  //   - !open                     当前是关着的（避免重复触发）
  //   - hasContent                现在有内容了
  useEffect(() => {
    if (hasContent && !open && !userDismissedRef.current) {
      setOpen(true);
    }
  }, [hasContent, open]);

  // 状态被清空（hasContent 从 true → false）时重置 dismiss 标记：
  // 新一轮 run 到来时用户应该能再看到自动展开。
  // 用 ref 记住上一次的 hasContent
  const prevHasContentRef = useRef<boolean>(hasContent);
  useEffect(() => {
    const prev = prevHasContentRef.current;
    if (prev && !hasContent) {
      // state 被清空（通常是新 session / 手动 resetState）
      userDismissedRef.current = false;
    }
    prevHasContentRef.current = hasContent;
  }, [hasContent]);

  // 用户手动 toggle 时记录态度
  const handleToggle = (next: boolean) => {
    setOpen(next);
    if (!next) {
      // 收起：标记"用户主动关过"，后续不再自动展开
      userDismissedRef.current = true;
    }
  };

  if (!hasContent && !open) {
    return null; // 没有 state 且折叠时，不渲染折叠条
  }

  return (
    <aside
      className={cn(
        'border-border bg-card text-card-foreground flex shrink-0 flex-col border-l',
        'transition-[width] duration-300 ease-out',
        open ? 'w-80' : 'w-9',
        className,
      )}
      aria-expanded={open}
    >
      {open ? (
        <>
          <div className="border-border flex h-14 shrink-0 items-center justify-between border-b px-3">
            <div className="flex items-center gap-2 text-sm font-semibold">
              <ListChecks size={16} />
              <span>执行状态</span>
              {/* 新增未读红点提示：内容有更新时显示 */}
              {hasContent && (
                <span className="bg-primary/15 text-primary rounded-full px-1.5 py-0.5 text-[10px] font-medium">
                  新
                </span>
              )}
            </div>
            <div className="flex items-center gap-1">
              <Button
                size="icon"
                variant="ghost"
                title="清空状态"
                onClick={resetState}
                className="h-7 w-7"
              >
                <Wrench size={14} />
              </Button>
              <Button
                size="icon"
                variant="ghost"
                title="收起"
                onClick={() => handleToggle(false)}
                className="h-7 w-7"
              >
                <X size={14} />
              </Button>
            </div>
          </div>
          <div
            className={cn(
              'flex-1 space-y-4 overflow-y-auto p-3 text-sm',
              'animate-in fade-in slide-in-from-right-2 duration-200',
            )}
          >
            <PlanSection plan={state.plan} />
            <ReviewSection review={state.review} />
            <CodeChangesSection changes={state.code_changes} />
            <CitationsSection citations={state.citations} />
            <FinalAnswerSection answer={state.final_answer} />
          </div>
        </>
      ) : (
        <button
          type="button"
          onClick={() => handleToggle(true)}
          className={cn(
            'text-muted-foreground hover:text-foreground hover:bg-muted/60',
            'flex h-full w-full flex-col items-center justify-start gap-2 py-3 transition-colors',
          )}
          title="展开状态面板"
        >
          <ListChecks size={16} className="-rotate-90" />
          {hasContent && (
            <span className="bg-primary text-primary-foreground flex h-4 min-w-4 items-center justify-center rounded-full px-1 text-[9px] font-medium">
              1
            </span>
          )}
        </button>
      )}
    </aside>
  );
}

// ---- 子区块 ---------------------------------------------------------------

function Section({
  title,
  icon: Icon,
  children,
}: {
  title: string;
  icon: LucideIcon;
  children: ReactNode;
}) {
  return (
    <section className="border-border bg-muted/30 rounded-md border p-3">
      <h3 className="text-foreground mb-2 flex items-center gap-1.5 text-xs font-semibold tracking-wider uppercase">
        <Icon size={14} />
        {title}
      </h3>
      {children}
    </section>
  );
}

function PlanSection({ plan }: { plan: PlanShape | undefined }) {
  if (!plan) return null;
  return (
    <Section title="计划" icon={ListChecks}>
      <div className="text-foreground mb-1.5 text-sm font-medium">{plan.goal}</div>
      {plan.rationale && (
        <p className="text-muted-foreground mb-2 text-xs leading-relaxed">{plan.rationale}</p>
      )}
      <ol className="text-foreground/90 list-decimal space-y-1 pl-5 text-xs">
        {plan.steps.map((s, i) => (
          <li key={s.id ?? i}>
            <span>{s.description}</span>
            {s.expected_output && (
              <span className="text-muted-foreground block">→ {s.expected_output}</span>
            )}
          </li>
        ))}
      </ol>
    </Section>
  );
}

function ReviewSection({ review }: { review: ReviewShape | undefined }) {
  if (!review) return null;
  const isApprove = review.verdict === 'approve';
  return (
    <Section title="评审" icon={isApprove ? CheckCircle2 : FileText}>
      <div
        className={cn(
          'mb-2 inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium',
          isApprove ? 'bg-green-100 text-green-700' : 'bg-amber-100 text-amber-700',
        )}
      >
        {isApprove ? '✓ 通过' : '⚠ 需修订'}
      </div>
      {review.issues.length > 0 && (
        <div className="mb-2">
          <div className="text-muted-foreground mb-1 text-[11px] font-medium tracking-wider uppercase">
            问题
          </div>
          <ul className="text-foreground/90 list-disc space-y-0.5 pl-5 text-xs">
            {review.issues.map((it, i) => (
              <li key={i}>{it}</li>
            ))}
          </ul>
        </div>
      )}
      {review.suggestions.length > 0 && (
        <div>
          <div className="text-muted-foreground mb-1 text-[11px] font-medium tracking-wider uppercase">
            建议
          </div>
          <ul className="text-foreground/90 list-disc space-y-0.5 pl-5 text-xs">
            {review.suggestions.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
        </div>
      )}
    </Section>
  );
}

function CodeChangesSection({ changes }: { changes: CodeChangeShape[] | undefined }) {
  if (!changes || changes.length === 0) return null;
  return (
    <Section title="代码变更" icon={FileText}>
      <ul className="text-foreground/90 space-y-2 text-xs">
        {changes.map((c, i) => (
          <li key={i} className="border-border bg-background rounded border p-2">
            <code className="text-primary font-mono text-[11px]">{c.file}</code>
            {c.description && <p className="text-muted-foreground mt-1">{c.description}</p>}
            {c.diff && (
              <pre className="bg-foreground/5 mt-1.5 overflow-x-auto rounded p-1.5 font-mono text-[11px] whitespace-pre">
                {c.diff}
              </pre>
            )}
          </li>
        ))}
      </ul>
    </Section>
  );
}

function CitationsSection({ citations }: { citations: CitationShape[] | undefined }) {
  if (!citations || citations.length === 0) return null;
  return (
    <Section title="引用" icon={Quote}>
      <ul className="text-foreground/90 space-y-1.5 text-xs">
        {citations.map((c, i) => (
          <li key={i} className="border-border bg-background rounded border p-2">
            <a
              href={c.url}
              target="_blank"
              rel="noreferrer noopener"
              className="text-primary break-all hover:underline"
            >
              {c.title || c.url}
            </a>
            {c.excerpt && <p className="text-muted-foreground mt-1 line-clamp-3">{c.excerpt}</p>}
          </li>
        ))}
      </ul>
    </Section>
  );
}

function FinalAnswerSection({ answer }: { answer: string | undefined }) {
  if (!answer) return null;
  return (
    <Section title="最终答案" icon={CheckCircle2}>
      <p className="text-foreground/90 text-xs leading-relaxed whitespace-pre-wrap">
        {answer}
      </p>
    </Section>
  );
}
