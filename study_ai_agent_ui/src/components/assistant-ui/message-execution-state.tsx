/**
 * 消息内联思考过程
 *
 * 把后端 ``STATE_SNAPSHOT`` 推过来的 plan / review / code_changes / citations
 * 内联到对应的 AI 消息气泡里，替代原先的右侧 StatePanel。
 *
 * 设计要点
 * --------
 * - 数据源：每条 AI 消息 ``metadata.custom.state``（见
 *   :func:`useChatController` 的实现），无需走全局 Context。
 * - 行为：
 *     - **生成中**：默认展开 plan / review / code_changes / citations，
 *       用户能看到"模型在思考什么"。
 *     - **生成完成**：默认收起，呈现为"思考过程"摘要按钮 + 数量角标，
 *       用户可点击展开查看细节；结果文本（``MessageParts``）依旧展示。
 * - 命名沿革：早期叫"执行过程"，但 panel 里展示的 plan / review 都是
 *   推理/反思阶段，``code_changes`` 才偏执行。改为"思考过程"更准确。
 * - 复用：section 渲染（plan / review / code_changes / citations）从
 *   老的 state-panel.tsx 迁过来；老的右侧面板组件会被删除。
 *
 * 关于 args-result 区域
 * ---------------------
 * LangChain 1.x 的 ``create_agent(response_format=Plan/Review)`` 会在
 * ``TOOL_CALL_START`` 事件里发出一个**合成**的 tool call（name="Plan" 或
 * "Review"，args 是 Pydantic 字段 JSON）。这个工具是 LangChain 用来把
 * LLM 输出强约束成结构化 JSON 的，**真实数据走 STATE_SNAPSHOT**，不会写
 * ``TOOL_CALL_RESULT``。后端在 SSE 流里已经把这个合成 tool call 的全部
 * 事件（START/ARGS/END/RESULT）过滤掉了（见
 * ``src/core/server.py::filter_structured_output_tool_events``），所以
 * 前端不会看到 args 像是 ``{verdict, issues, suggestions}`` 且 result
 * 永远为空的工具块。
 */
import { useState, type FC, type ReactNode } from 'react';
import { useMessage } from '@assistant-ui/react';
import {
  ChevronDown,
  CheckCircle2,
  FileText,
  ListChecks,
  Quote,
  Wrench,
  AlertTriangle,
  type LucideIcon,
} from 'lucide-react';

import { cn } from '@/lib/utils';
import type {
  AguiStateSnapshot,
  CitationShape,
  CodeChangeShape,
  PlanShape,
  ReviewShape,
} from '@/lib/agui';

/**
 * 渲染条件：state 存在 + 至少有一个有内容的字段；否则返回 null。
 * 不会重复显示在 Chat 顶部 / 其它位置 —— 它就是这条消息专属的执行状态。
 */
export const MessageExecutionState: FC = () => {
  // selector 返回的是同一个引用，zustand 默认 Object.is 比较；这里没创建新对象
  const state = useMessage(
    (m): AguiStateSnapshot | undefined =>
      (m.metadata?.custom?.state as AguiStateSnapshot | undefined) ?? undefined,
  );
  const isRunning = useMessage((m) => m.status?.type === 'running');
  // 用户手动展开的开关：完成态默认收起，点一下能展开看完整过程
  const [manuallyExpanded, setManuallyExpanded] = useState(false);

  if (!state) return null;

  const hasPlan = Boolean(state.plan);
  const hasReview = Boolean(state.review);
  const citationsCount = state.citations?.length ?? 0;
  const codeChangesCount = state.code_changes?.length ?? 0;
  const totalCount =
    (hasPlan ? 1 : 0) +
    (hasReview ? 1 : 0) +
    citationsCount +
    codeChangesCount;

  // 完全没内容（只有空 final_answer 之类）时也不要渲染
  if (totalCount === 0) return null;

  const expanded = isRunning || manuallyExpanded;

  return (
    <div
      className={cn(
        'border-border bg-muted/30 my-2 overflow-hidden rounded-md border text-xs',
        isRunning && 'border-primary/30',
      )}
    >
      <button
        type="button"
        onClick={() => setManuallyExpanded((v) => !v)}
        className={cn(
          'text-foreground hover:bg-muted/60 flex w-full flex-wrap items-center gap-x-2 gap-y-1 px-3 py-1.5 text-left transition-colors',
        )}
        aria-expanded={expanded}
      >
        <span className="flex shrink-0 items-center gap-1.5">
          <ChevronDown
            className={cn(
              'text-muted-foreground h-3 w-3 transition-transform',
              !expanded && '-rotate-90',
            )}
          />
          <Wrench className="text-muted-foreground h-3 w-3" />
          <span className="font-medium">
          {isRunning ? '正在思考…' : '思考过程'}
        </span>
        </span>

        {/* 数量角标 —— 让用户一眼看到过程有多复杂；窄屏可换行 */}
        <div className="text-muted-foreground ml-1 flex flex-wrap items-center gap-1.5">
          {hasPlan && (
            <span className="bg-background rounded-full px-1.5 py-0.5 font-mono text-[10px]">
              计划 {state.plan!.steps.length} 步
            </span>
          )}
          {hasReview && (
            <span
              className={cn(
                'rounded-full px-1.5 py-0.5 font-mono text-[10px]',
                state.review!.verdict === 'approve'
                  ? 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300'
                  : 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300',
              )}
            >
              {state.review!.verdict === 'approve' ? '审核 ✓' : '审核 ⚠'}
            </span>
          )}
          {citationsCount > 0 && (
            <span className="bg-background rounded-full px-1.5 py-0.5 font-mono text-[10px]">
              引用 ×{citationsCount}
            </span>
          )}
          {codeChangesCount > 0 && (
            <span className="bg-background rounded-full px-1.5 py-0.5 font-mono text-[10px]">
              变更 ×{codeChangesCount}
            </span>
          )}
        </div>
      </button>

      {expanded && (
        <div
          className={cn(
            'border-border space-y-3 border-t px-3 py-2.5',
            'animate-in fade-in slide-in-from-top-1 duration-200',
          )}
        >
          <PlanSection plan={state.plan} />
          <ReviewSection review={state.review} />
          <CodeChangesSection changes={state.code_changes} />
          <CitationsSection citations={state.citations} />
        </div>
      )}
    </div>
  );
};

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
    <section>
      <h4 className="text-muted-foreground mb-1.5 flex items-center gap-1.5 text-[11px] font-semibold tracking-wider uppercase">
        <Icon size={12} />
        {title}
      </h4>
      <div className="text-foreground/90 space-y-1.5">{children}</div>
    </section>
  );
}

function PlanSection({ plan }: { plan: PlanShape | undefined }) {
  if (!plan) return null;
  return (
    <Section title="计划" icon={ListChecks}>
      <div className="text-foreground text-xs font-medium">{plan.goal}</div>
      {plan.rationale && (
        <p className="text-muted-foreground text-[11px] leading-relaxed">
          {plan.rationale}
        </p>
      )}
      {plan.steps.length > 0 && (
        <ol className="text-foreground/90 list-decimal space-y-0.5 pl-5 text-[11px]">
          {plan.steps.map((s, i) => (
            <li key={s.id ?? i}>
              <span>{s.description}</span>
              {s.expected_output && (
                <span className="text-muted-foreground block">
                  → {s.expected_output}
                </span>
              )}
            </li>
          ))}
        </ol>
      )}
    </Section>
  );
}

function ReviewSection({ review }: { review: ReviewShape | undefined }) {
  if (!review) return null;
  const isApprove = review.verdict === 'approve';
  return (
    <Section
      title="评审"
      icon={isApprove ? CheckCircle2 : AlertTriangle}
    >
      <div
        className={cn(
          'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium',
          isApprove
            ? 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300'
            : 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300',
        )}
      >
        {isApprove ? '✓ 通过' : '⚠ 需修订'}
      </div>
      {review.issues.length > 0 && (
        <div>
          <div className="text-muted-foreground mb-0.5 text-[10px] font-medium tracking-wider uppercase">
            问题
          </div>
          <ul className="text-foreground/90 list-disc space-y-0.5 pl-5 text-[11px]">
            {review.issues.map((it, i) => (
              <li key={i}>{it}</li>
            ))}
          </ul>
        </div>
      )}
      {review.suggestions.length > 0 && (
        <div>
          <div className="text-muted-foreground mb-0.5 text-[10px] font-medium tracking-wider uppercase">
            建议
          </div>
          <ul className="text-foreground/90 list-disc space-y-0.5 pl-5 text-[11px]">
            {review.suggestions.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
        </div>
      )}
    </Section>
  );
}

function CodeChangesSection({
  changes,
}: {
  changes: CodeChangeShape[] | undefined;
}) {
  if (!changes || changes.length === 0) return null;
  return (
    <Section title="代码变更" icon={FileText}>
      <ul className="space-y-1.5">
        {changes.map((c, i) => (
          <li
            key={i}
            className="border-border bg-background rounded border p-2 text-[11px]"
          >
            <code className="text-primary font-mono text-[11px]">{c.file}</code>
            {c.description && (
              <p className="text-muted-foreground mt-1 text-[11px]">
                {c.description}
              </p>
            )}
            {c.diff && (
              <pre className="bg-foreground/5 mt-1.5 max-h-40 overflow-x-auto rounded p-1.5 font-mono text-[10px] whitespace-pre">
                {c.diff}
              </pre>
            )}
          </li>
        ))}
      </ul>
    </Section>
  );
}

function CitationsSection({
  citations,
}: {
  citations: CitationShape[] | undefined;
}) {
  if (!citations || citations.length === 0) return null;
  return (
    <Section title="引用" icon={Quote}>
      <ul className="space-y-1.5">
        {citations.map((c, i) => (
          <li
            key={i}
            className="border-border bg-background rounded border p-2 text-[11px]"
          >
            <a
              href={c.url}
              target="_blank"
              rel="noreferrer noopener"
              className="text-primary break-all hover:underline"
            >
              {c.title || c.url}
            </a>
            {c.excerpt && (
              <p className="text-muted-foreground mt-1 line-clamp-3 text-[11px]">
                {c.excerpt}
              </p>
            )}
          </li>
        ))}
      </ul>
    </Section>
  );
}
