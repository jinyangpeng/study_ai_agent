/**
 * Thread 组件
 *
 * 封装 assistant-ui 的 ThreadPrimitive 集合，用 Tailwind 做样式。
 * 设计参照 shadcn/ui 官方示例 + AI Studio 风格：渐变欢迎区、quick prompt 卡片、
 * 消息操作行（复制 / 重新生成）。
 *
 * 生成期 UI 设计
 * --------------
 * - AI 消息气泡（思考过程 → 结果 顺序）：
 *     1. MessageExecutionState：内联在每条 AI 消息里，渲染 plan / review /
 *        code_changes / citations；运行中默认展开，完成后默认收起，可手动展开。
 *     2. 文本 / 工具调用：内容为空 + running → 显示思考点（ThinkingDots）；
 *        有内容 → Markdown + ToolFallback。
 * - Tool 调用：args 已就绪但 result 未到 → 显示"调用中…"loader
 *   （注：后端会过滤掉 Plan / Review 等 LangChain 内部结构化输出合成工具）
 * - Composer 顶部：醒目 banner 提示"正在生成"，含 cancel 引导
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import {
  ActionBarPrimitive,
  ComposerPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
  useMessage,
  useThread,
} from '@assistant-ui/react';
import {
  ArrowDownIcon,
  Check,
  Copy,
  Loader2,
  RefreshCw,
  SendHorizontalIcon,
  SquareIcon,
  Sparkles,
  Code2,
  Compass,
  BookOpen,
  Lightbulb,
  Wrench,
  Search,
  FileText,
  HelpCircle,
  Calculator,
  Globe,
  ListChecks,
  MessageSquare,
  User,
  type LucideIcon,
} from 'lucide-react';
import type { FC } from 'react';

import { MarkdownText } from './markdown-text';
import { ToolFallback } from './tool-fallback';
import { MessageExecutionState } from './message-execution-state';
import { Button } from './ui/button';
import { useSkill, useAguiState } from '@/context';
import { cn } from '@/lib/utils';
import type { QuickPrompt } from '@/features/skills';

// ---- Root --------------------------------------------------------------

export const Thread: FC<{ className?: string }> = ({ className }) => (
  <ThreadPrimitive.Root
    className={cn(
      'bg-background box-border flex h-full flex-col overflow-hidden',
      className,
    )}
  >
    {/* 滚动容器：内部用一个 ``w-full`` 容器把消息、欢迎区、滚回最新按钮
        都"撑满可用宽度"。原本写成 ``max-w-2xl mx-auto`` 在 2xl 屏（>= 1024px）
        外会产生大量左右留白，且隐藏侧栏后内容也不会扩展 —— 现在去掉
        ``max-w-2xl``，让 wrapper 跟随 viewport 自适应；消息冒泡由内层
        ``max-w-[calc(100%-3rem)]``（减去 32px 头像 + 8px gap）兜底。

        对应的 Composer 容器（见下方）也同步去掉 max-w-2xl，宽度跟消息对齐。 */}
    <ThreadPrimitive.Viewport className="aui-thread-viewport flex h-full flex-col items-stretch overflow-y-scroll pt-8">
      <div className="flex w-full flex-col items-stretch px-14 sm:px-16 lg:px-18">
        <ThreadPrimitive.Empty>
          <ThreadWelcome />
        </ThreadPrimitive.Empty>

        <ThreadPrimitive.Messages
          components={{
            UserMessage,
            EditComposer,
            AssistantMessage,
          }}
        />

        {/* 浮动在右下角的"回到最新"按钮 —— 跟消息一起撑满宽度，依然靠右 */}
        <div className="sticky bottom-2 mt-2 flex justify-end">
          <ThreadScrollToBottom />
        </div>
      </div>
    </ThreadPrimitive.Viewport>

    <div className="sticky bottom-0 mt-auto flex w-full flex-col items-stretch self-center px-20 pb-20 sm:px-22 lg:px-24">
      <Composer />
    </div>
  </ThreadPrimitive.Root>
);

// ---- Welcome (empty state) ---------------------------------------------

/** lucide-react 图标名 → 组件 映射（覆盖三个 skill 用到的图标） */
const ICON_MAP: Record<string, LucideIcon> = {
  Code2,
  Compass,
  BookOpen,
  Lightbulb,
  Wrench,
  Search,
  FileText,
  HelpCircle,
  Calculator,
  Globe,
  ListChecks,
  MessageSquare,
};

/** 没有 quick_prompts 时用的通用兜底 */
const FALLBACK_QUICK_PROMPTS: QuickPrompt[] = [
  {
    icon: 'MessageSquare',
    title: '随便聊聊',
    description: '跟当前智能体打个招呼',
    prompt: '你好，请简单介绍一下你自己能做什么。',
  },
];

const ThreadWelcome: FC = () => {
  const skill = useSkill();

  // 优先使用后端声明的 quick_prompts，没有再回退到通用兜底
  const prompts = skill.current?.quick_prompts?.length
    ? skill.current.quick_prompts
    : FALLBACK_QUICK_PROMPTS;

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col items-center justify-center gap-6 px-2 py-8 text-center sm:gap-8 sm:px-4 sm:py-10">
      {/* 品牌区 */}
      <div className="flex flex-col items-center gap-3 sm:gap-4">
        <div className="from-primary to-primary/70 text-primary-foreground flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br shadow-lg sm:h-16 sm:w-16">
          <Sparkles size={24} className="sm:hidden" />
          <Sparkles size={28} className="hidden sm:block" />
        </div>
        <div className="flex flex-col gap-1">
          <h1 className="text-foreground text-xl font-semibold tracking-tight sm:text-2xl">
            你好，欢迎使用 Study AI Agent
          </h1>
          <p className="text-muted-foreground px-2 text-xs leading-relaxed sm:text-sm">
            当前智能体：
            <span className="text-foreground font-medium">
              {skill.current?.name ?? skill.currentSkill}
            </span>
            <span className="mx-2 opacity-50">·</span>
            {skill.current?.description ?? '选择左侧智能体开始体验'}
          </p>
        </div>
      </div>

      {/* Quick prompts —— 由后端 skill 声明，跟当前 agent 绑定 */}
      <div className="grid w-full grid-cols-1 gap-2.5 sm:grid-cols-2 sm:gap-3">
        {prompts.map((qp, idx) => (
          <QuickPrompt
            key={`${skill.currentSkill}-${idx}-${qp.prompt}`}
            iconName={qp.icon}
            title={qp.title}
            description={qp.description}
            prompt={qp.prompt}
          />
        ))}
      </div>
    </div>
  );
};

function QuickPrompt({
  iconName,
  title,
  description,
  prompt,
}: {
  iconName: string;
  title: string;
  description: string;
  prompt: string;
}) {
  const Icon = ICON_MAP[iconName] ?? MessageSquare;
  return (
    <ThreadPrimitive.Suggestion
      prompt={prompt}
      className={cn(
        'group border-border bg-card text-card-foreground',
        'hover:border-primary/50 hover:bg-accent/40 hover:shadow-md',
        'flex flex-col items-start gap-1.5 rounded-xl border p-4 text-left transition-all',
      )}
    >
      <div className="flex w-full items-center gap-2">
        <div className="bg-muted text-muted-foreground group-hover:bg-primary/10 group-hover:text-primary flex h-7 w-7 items-center justify-center rounded-md transition-colors">
          <Icon size={14} />
        </div>
        <div className="text-sm font-medium">{title}</div>
      </div>
      <div className="text-muted-foreground text-xs leading-relaxed">{description}</div>
      <div className="text-foreground/70 group-hover:text-foreground mt-1 line-clamp-1 text-xs italic transition-colors">
        {prompt}
      </div>
    </ThreadPrimitive.Suggestion>
  );
}

// ---- Local helpers -----------------------------------------------------

const MessageParts: FC<{ text: boolean; tools?: boolean }> = ({ text, tools }) => (
  <MessagePrimitive.Parts
    components={{
      ...(text ? { Text: MarkdownText } : null),
      ...(tools ? { tools: { Fallback: ToolFallback } } : null),
    }}
  />
);

/** 相对时间：刚刚 / N 分钟前 / HH:MM / YYYY-MM-DD */
function formatRelativeTime(d: Date | string | number | undefined): string {
  if (!d) return '';
  const date = d instanceof Date ? d : new Date(d);
  if (Number.isNaN(date.getTime())) return '';
  const now = Date.now();
  const diff = Math.max(0, now - date.getTime());
  if (diff < 30 * 1000) return '刚刚';
  if (diff < 60 * 1000) return `${Math.floor(diff / 1000)} 秒前`;
  if (diff < 60 * 60 * 1000) return `${Math.floor(diff / 60_000)} 分钟前`;
  if (diff < 24 * 60 * 60 * 1000) {
    return `${date.getHours().toString().padStart(2, '0')}:${date
      .getMinutes()
      .toString()
      .padStart(2, '0')}`;
  }
  return `${date.getMonth() + 1}/${date.getDate()}`;
}

/** 让时间戳文字每 30s 刷新一次（仅当消息 < 1 小时时） */
function useTickingTimestamp(date: Date | string | number | undefined): string {
  const [text, setText] = useState(() => formatRelativeTime(date));
  useEffect(() => {
    setText(formatRelativeTime(date));
    const d = date instanceof Date ? date : date ? new Date(date) : null;
    if (!d) return;
    const ageMs = Date.now() - d.getTime();
    if (ageMs > 60 * 60 * 1000) return; // 超过 1 小时不再刷新
    const interval = ageMs < 60 * 1000 ? 5_000 : 30_000;
    const id = window.setInterval(() => setText(formatRelativeTime(date)), interval);
    return () => window.clearInterval(id);
  }, [date]);
  return text;
}

const MessageTimestamp: FC<{ date: Date | string | number | undefined }> = ({ date }) => {
  const text = useTickingTimestamp(date);
  if (!text) return null;
  return (
    <span
      className="text-muted-foreground/70 text-[10px] tabular-nums"
      title={date instanceof Date ? date.toLocaleString() : new Date(date!).toLocaleString()}
    >
      {text}
    </span>
  );
};

// ---- Thinking dots -----------------------------------------------------

/**
 * AI 正在"思考"时的占位动画 —— assistant-ui 还没有暴露内容到气泡时
 * 用三个小圆点跳一下表达"在干活了"，比空气泡友好得多。
 */
const ThinkingDots: FC = () => (
  <div
    className="text-muted-foreground flex items-center gap-1.5 py-2"
    role="status"
    aria-label="AI 正在思考"
  >
    <span
      className="bg-primary/60 h-1.5 w-1.5 rounded-full animate-bounce"
      style={{ animationDelay: '0ms' }}
    />
    <span
      className="bg-primary/60 h-1.5 w-1.5 rounded-full animate-bounce"
      style={{ animationDelay: '150ms' }}
    />
    <span
      className="bg-primary/60 h-1.5 w-1.5 rounded-full animate-bounce"
      style={{ animationDelay: '300ms' }}
    />
    <span className="text-muted-foreground ml-1 text-xs">正在思考…</span>
  </div>
);

// ---- Messages ---------------------------------------------------------

const UserMessage: FC = () => {
  const createdAt = useMessage((s) => s.createdAt);
  return (
    <MessagePrimitive.Root className="group/user relative mb-5 flex w-full items-end justify-end gap-2 py-1">
      {/* 内容列 —— 靠右，最大宽度为父容器减去头像 32px + 8px gap
          （``calc(100%-3rem)``）；不再加 ``sm:max-w-2xl``，让气泡
          跟随 wrapper 撑满可用宽度。 */}
      <div className="flex min-w-0 max-w-[calc(100%-3rem)] flex-col items-end">
        <div className="bg-muted text-foreground rounded-2xl rounded-tr-md px-4 py-2.5 break-words shadow-sm">
          <MessageParts text />
          <div className="text-muted-foreground/80 mt-1 flex justify-end">
            <MessageTimestamp date={createdAt} />
          </div>
        </div>

        {/* hover 时显示复制 / 编辑 —— assistant-ui 自带 */}
        <MessagePrimitive.If user>
          <UserActions />
        </MessagePrimitive.If>
      </div>

      {/* 用户头像 —— 蓝色渐变 + User 图标，靠右 + 顶部对齐（多行消息时不跟着内容底） */}
      <div
        className="flex h-8 w-8 shrink-0 items-center justify-center self-start rounded-full bg-gradient-to-br from-blue-500 to-indigo-500 text-white shadow-sm"
        aria-hidden
      >
        <User size={16} />
      </div>
    </MessagePrimitive.Root>
  );
};

/** 用户消息底部的操作行：复制 + 编辑，仅在 hover 时显示。 */
const UserActions: FC = () => {
  const [copied, setCopied] = useState(false);

  // 消息切换时清掉 copied 状态
  useEffect(() => {
    setCopied(false);
  }, []);

  return (
    <div className="text-muted-foreground mt-1 flex items-center justify-end gap-1 opacity-0 transition-opacity group-hover/user:opacity-100">
      <ActionBarPrimitive.Copy
        className={cn(
          'hover:bg-muted hover:text-foreground inline-flex h-6 items-center gap-1 rounded px-1.5 text-[10px] transition-colors',
          copied && 'text-green-600 dark:text-green-400',
        )}
        copiedDuration={1800}
        onClick={() => {
          setCopied(true);
          setTimeout(() => setCopied(false), 1800);
        }}
        title="复制"
      >
        {copied ? <Check size={12} /> : <Copy size={12} />}
        <span>{copied ? '已复制' : '复制'}</span>
      </ActionBarPrimitive.Copy>
      <ActionBarPrimitive.Edit
        className="hover:bg-muted hover:text-foreground inline-flex h-6 items-center gap-1 rounded px-1.5 text-[10px] transition-colors"
        title="编辑"
      >
        <span>编辑</span>
      </ActionBarPrimitive.Edit>
    </div>
  );
};

/**
 * 判断消息"是否有内容"：空字符串 / 空数组 / 全是空 text part 视为无内容。
 * tool-call 只要存在就算"有内容"（即便 result 还没回来）。
 */
function useHasMessageContent(): boolean {
  // 显式声明返回类型为 unknown —— useMessage 在不同 role 下推断的 content 类型
  // 是不一样的（比如 user 是 string，assistant 是 ContentPart[]），不指定
  // 会得到 never，导致 `.length` / `.some` 等调用报 TS2339。
  const content = useMessage((s): unknown => s.content) as unknown;
  return useMemo<boolean>(() => {
    if (content == null) return false;
    if (typeof content === 'string') return content.length > 0;
    if (Array.isArray(content)) {
      return content.some((p) => {
        if (!p || typeof p !== 'object') return false;
        const part = p as { type?: string; text?: string };
        if (part.type === 'text') return Boolean(part.text);
        if (part.type === 'tool-call') return true;
        return Boolean((part as { text?: string }).text);
      });
    }
    return true;
  }, [content]);
}

const AssistantMessage: FC = () => {
  const createdAt = useMessage((s) => s.createdAt);
  const isRunning = useMessage((s) => s.status?.type === 'running');

  return (
    <MessagePrimitive.Root className="group/assist relative mb-5 flex w-full items-start justify-start gap-2 py-1">
      {/* AI 头像 —— 靠左 */}
      <div className="from-primary to-primary/70 text-primary-foreground flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br text-xs font-semibold shadow-sm">
        AI
      </div>

      {/* 内容列 —— 靠左，宽度跟 wrapper 一起撑满（减去左侧头像 32px + 8px gap） */}
      <div className="flex min-w-0 max-w-[calc(100%-3rem)] flex-1 flex-col">
        <MessagePrimitive.If assistant>
          <AssistantMessageBody />
        </MessagePrimitive.If>

        {/* 时间戳 + 生成中状态 */}
        <div className="text-muted-foreground/80 mt-1 flex items-center gap-2">
          <MessageTimestamp date={createdAt} />
          {isRunning && (
            <span className="text-primary/80 inline-flex items-center gap-1 text-[10px] font-medium">
              <Loader2 className="h-3 w-3 animate-spin" />
              生成中…
            </span>
          )}
        </div>

        {/* 操作行：复制 / 重新生成 / 反馈 */}
        <div className="mt-1.5 flex items-center gap-0.5 opacity-0 transition-opacity group-hover/assist:opacity-100">
          <MessagePrimitive.If assistant>
            <AssistantActions />
          </MessagePrimitive.If>
        </div>
      </div>
    </MessagePrimitive.Root>
  );
};

/**
 * AI 消息主体
 *
 * 顺序（满足"过程在结果之前"的产品要求）：
 *   1. MessageExecutionState —— 后端 plan/review/code_changes/citations 内联展示
 *      （运行中默认展开，完成后默认收起，可手动展开看完整过程）
 *   2. ThinkingDots / MessageParts —— 文本与工具调用
 *      （内容为空 + running 时显示思考点，否则渲染实际内容）
 *
 * 错误态：独立的红色边框 + ⚠ 文本，与正常消息区分。
 */
const AssistantMessageBody: FC = () => {
  const isError = useMessage((s): boolean => {
    const st = s.status;
    return st?.type === 'incomplete' && 'reason' in st && st.reason === 'error';
  });
  const hasContent = useHasMessageContent();
  const isRunning = useMessage((s) => s.status?.type === 'running');

  if (isError) {
    return (
      <div
        className="border-destructive/40 bg-destructive/5 text-destructive rounded-md border px-3 py-2"
        data-error="true"
      >
        <MessageParts text tools />
      </div>
    );
  }

  return (
    <div className="rounded-md">
      {/* 1) 执行过程 —— 内联在消息里，运行中展开、完成后收起 */}
      <MessageExecutionState />
      {/* 2) 思考点 / 实际内容 */}
      {isRunning && !hasContent ? <ThinkingDots /> : <MessageParts text tools />}
    </div>
  );
};

const AssistantActions: FC = () => {
  const [copied, setCopied] = useState(false);

  // 重置 copied（消息变化时）
  useEffect(() => {
    setCopied(false);
  }, []);

  return (
    <div className="text-muted-foreground flex items-center gap-0.5">
      <ActionBarPrimitive.Copy
        className={cn(
          'hover:bg-muted hover:text-foreground inline-flex h-7 items-center gap-1 rounded px-1.5 text-[10px] transition-colors',
          copied && 'text-green-600 dark:text-green-400',
        )}
        copiedDuration={1800}
        onClick={() => {
          setCopied(true);
          setTimeout(() => setCopied(false), 1800);
        }}
        title="复制"
      >
        {copied ? <Check size={12} /> : <Copy size={12} />}
        <span>{copied ? '已复制' : '复制'}</span>
      </ActionBarPrimitive.Copy>

      <ActionBarPrimitive.Reload
        className="hover:bg-muted hover:text-foreground inline-flex h-7 items-center gap-1 rounded px-1.5 text-[10px] transition-colors"
        title="重新生成"
      >
        <RefreshCw size={12} />
        <span>重新生成</span>
      </ActionBarPrimitive.Reload>
    </div>
  );
};

const EditComposer: FC = () => (
  <ComposerPrimitive.Root className="bg-muted/40 my-4 flex w-full max-w-2xl flex-col gap-2 rounded-lg border p-2">
    <ComposerPrimitive.Input
      className="text-foreground placeholder:text-muted-foreground min-h-12 w-full resize-none border-none bg-transparent px-2 py-1.5 text-sm outline-none focus:outline-none"
      autoFocus
    />
    <div className="flex justify-end gap-2">
      <ComposerPrimitive.Cancel>
        <Button variant="ghost" size="sm">
          取消
        </Button>
      </ComposerPrimitive.Cancel>
      <ComposerPrimitive.Send>
        <Button size="sm">保存</Button>
      </ComposerPrimitive.Send>
    </div>
  </ComposerPrimitive.Root>
);

// ---- Composer ---------------------------------------------------------

/**
 * 在 running 时显示在 Composer 上方的小提示。
 * 比之前单行 "正在生成回复…" 更醒目，且包含"如何停止"的引导。
 *
 * 与 stage 联动 —— 后端 STEP_STARTED 事件推过来的 step_name 会被实时展示，
 * 比如"正在制定计划"、"正在执行查询"。stage 为空时回退到通用文案。
 */
const STAGE_LABELS: Record<string, string> = {
  plan: '正在制定计划',
  planning: '正在制定计划',
  execute: '正在执行',
  executing: '正在执行',
  review: '正在审核结果',
  reviewing: '正在审核结果',
  aggregate: '正在汇总结果',
  aggregating: '正在汇总结果',
  tool: '正在调用工具',
  tool_call: '正在调用工具',
};

const ComposerRunningBanner: FC = () => {
  const isRunning = useThread((s) => s.isRunning);
  const { currentStage } = useAguiState();
  if (!isRunning) return null;

  // 阶段文案：优先用映射表里的中文名，否则把 snake_case 简单转成中文友好形式
  const stageText = currentStage
    ? (STAGE_LABELS[currentStage] ??
        `正在执行：${currentStage.replace(/_/g, ' ').toLowerCase()}`)
    : null;

  return (
    <div
      className="border-primary/20 bg-primary/5 text-foreground mx-auto mb-2 flex w-full max-w-2xl animate-pulse items-center gap-2 rounded-lg border px-3 py-1.5 text-xs"
      role="status"
      aria-live="polite"
    >
      <Loader2 className="text-primary h-3.5 w-3.5 animate-spin" />
      <span className="font-medium">{stageText ?? '正在生成回复'}</span>
      {stageText && (
        <span className="text-muted-foreground font-mono text-[10px] tracking-wider uppercase opacity-70">
          · {currentStage}
        </span>
      )}
      <span className="text-muted-foreground ml-auto">可点击输入框旁的 ⏹ 停止</span>
    </div>
  );
};

const Composer: FC = () => (
  <>
    <ComposerRunningBanner />
    <ComposerPrimitive.Root className="bg-background border-border focus-within:border-ring/50 shadow-sm hover:shadow-md mx-auto flex w-full flex-col rounded-2xl border p-2 transition-all">
      <ComposerPrimitive.Input
        placeholder="发消息... (Ctrl/⌘+Enter 发送)"
        className="text-foreground placeholder:text-muted-foreground max-h-40 min-h-10 w-full flex-1 resize-none border-none bg-transparent px-3 py-2 text-sm outline-none focus:outline-none"
        rows={1}
        // 让 Enter 发送、Shift+Enter 换行
        onKeyDown={(e) => {
          if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
            // 让 assistant-ui 处理发送（按钮的 onClick）
            const form = (e.currentTarget as HTMLTextAreaElement).form;
            if (form) form.requestSubmit();
            e.preventDefault();
          }
        }}
      />
      <div className="flex items-center justify-end gap-2 px-1 pt-1">
        <ThreadPrimitive.Empty>
          <ThreadSuggestionRow />
        </ThreadPrimitive.Empty>
        <ComposerAction />
      </div>
    </ComposerPrimitive.Root>
  </>
);

const ComposerAction: FC = () => {
  return (
    <>
      <ThreadPrimitive.If running={false}>
        <ComposerPrimitive.Send
          className={cn(
            'bg-primary text-primary-foreground hover:bg-primary/90 inline-flex h-8 w-8 items-center justify-center rounded-md transition-colors',
          )}
        >
          <SendHorizontalIcon className="h-4 w-4" />
        </ComposerPrimitive.Send>
      </ThreadPrimitive.If>
      <ThreadPrimitive.If running>
        <ComposerPrimitive.Cancel
          className={cn(
            'bg-destructive text-destructive-foreground hover:bg-destructive/90 inline-flex h-8 w-8 items-center justify-center rounded-md transition-colors',
          )}
          title="停止生成"
        >
          <SquareIcon className="h-4 w-4" fill="currentColor" />
        </ComposerPrimitive.Cancel>
      </ThreadPrimitive.If>
    </>
  );
};

const ThreadSuggestionRow: FC = () => {
  const suggestions = [
    '用 Python 写一个快排',
    '总结 2025 LLM Agent 趋势',
    '解释一下 src/core/nodes.py 的作用',
  ];
  return (
    <div className="flex flex-1 flex-wrap gap-1.5">
      {suggestions.map((text) => (
        <ThreadPrimitive.Suggestion
          key={text}
          prompt={text}
          className="bg-muted hover:bg-muted/70 text-muted-foreground rounded-full px-3 py-1 text-xs transition-colors"
        />
      ))}
    </div>
  );
};

// ---- Scroll to bottom indicator ---------------------------------------

/**
 * 监听 thread 消息数量变化，自动把 viewport 滚到最底。
 * 关键是只在消息"增加"时滚（用户主动上滑时不要强行拽回）。
 */
const useAutoScrollOnNewMessage = (): void => {
  // 拿到 thread 的消息数
  const messageCount = useThread((s) => s.messages.length);
  // 上次已见到的消息数（用 ref 持久）
  const lastCountRef = useRef<number>(messageCount);
  useEffect(() => {
    // 仅在数量增加时滚动（更安全：用户删除/编辑不滚）
    if (messageCount > lastCountRef.current) {
      const scroller = document.querySelector(
        '.aui-thread-viewport',
      ) as HTMLElement | null;
      if (scroller) {
        // 用户已经接近底部才自动滚；否则只点亮 ScrollToBottom 按钮
        const nearBottom =
          scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight < 200;
        if (nearBottom) {
          requestAnimationFrame(() => {
            scroller.scrollTo({ top: scroller.scrollHeight, behavior: 'smooth' });
          });
        }
      }
    }
    lastCountRef.current = messageCount;
  }, [messageCount]);
};

export const ThreadScrollToBottom: FC = () => {
  useAutoScrollOnNewMessage();
  return (
    <ThreadPrimitive.ScrollToBottom className="bg-background text-muted-foreground hover:text-foreground inline-flex h-8 w-8 items-center justify-center rounded-full border shadow-sm transition-colors">
      <ArrowDownIcon className="h-4 w-4" />
    </ThreadPrimitive.ScrollToBottom>
  );
};
