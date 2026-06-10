/**
 * Thread 组件
 *
 * 封装 assistant-ui 的 ThreadPrimitive 集合，用 Tailwind 做样式。
 * 设计参照 shadcn/ui 官方示例 + AI Studio 风格：渐变欢迎区、quick prompt 卡片、
 * 消息操作行（复制 / 重新生成 / 反馈）。
 */
import { useState, useEffect, useRef } from 'react';
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
  ThumbsDown,
  ThumbsUp,
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
  type LucideIcon,
} from 'lucide-react';
import type { FC } from 'react';

import { MarkdownText } from './markdown-text';
import { ToolFallback } from './tool-fallback';
import { Button } from './ui/button';
import { useSkill } from '@/context';
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
    <ThreadPrimitive.Viewport className="aui-thread-viewport flex h-full flex-col items-stretch overflow-y-scroll px-4 pt-8">
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

      {/* 浮动在右下角的"回到最新"按钮 —— 同时承担自动滚动触发职责 */}
      <div className="sticky bottom-2 mt-2 mr-1 flex justify-end">
        <ThreadScrollToBottom />
      </div>
    </ThreadPrimitive.Viewport>

    <div className="sticky bottom-0 mt-auto flex w-full max-w-2xl flex-col items-stretch self-center px-4 pb-4">
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
    <div className="mx-auto flex w-full max-w-2xl flex-col items-center justify-center gap-8 px-4 py-10 text-center">
      {/* 品牌区 */}
      <div className="flex flex-col items-center gap-4">
        <div className="from-primary to-primary/70 text-primary-foreground flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br shadow-lg">
          <Sparkles size={28} />
        </div>
        <div className="flex flex-col gap-1">
          <h1 className="text-foreground text-2xl font-semibold tracking-tight">
            你好，欢迎使用 Study AI Agent
          </h1>
          <p className="text-muted-foreground text-sm">
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
      <div className="grid w-full grid-cols-1 gap-3 sm:grid-cols-2">
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

// ---- Messages ---------------------------------------------------------

const UserMessage: FC = () => {
  const createdAt = useMessage((s) => s.createdAt);
  return (
    <MessagePrimitive.Root className="group/user relative mb-5 grid w-full max-w-2xl auto-rows-auto grid-cols-[minmax(0,1fr)_auto] items-end gap-x-2 py-1">
      <div className="bg-muted text-foreground col-start-2 max-w-[80%] rounded-2xl rounded-br-md px-4 py-2.5 break-words whitespace-pre-wrap shadow-sm">
        <MessageParts text />
        <div className="text-muted-foreground/80 mt-1 flex justify-end">
          <MessageTimestamp date={createdAt} />
        </div>
      </div>
      {/* hover 时显示编辑按钮（assistant-ui 自带） */}
      <MessagePrimitive.If user>
        <div className="text-muted-foreground col-start-2 mr-1 flex items-center justify-end gap-1 opacity-0 transition-opacity group-hover/user:opacity-100">
          <ActionBarPrimitive.Edit
            className="hover:bg-muted hover:text-foreground inline-flex h-6 items-center gap-1 rounded px-1.5 text-[10px] transition-colors"
            title="编辑"
          >
            <span>编辑</span>
          </ActionBarPrimitive.Edit>
        </div>
      </MessagePrimitive.If>
    </MessagePrimitive.Root>
  );
};

const AssistantMessage: FC = () => {
  const createdAt = useMessage((s) => s.createdAt);
  const isRunning = useMessage((s) => s.status?.type === 'running');
  return (
    <MessagePrimitive.Root className="group/assist relative mb-5 grid w-full max-w-2xl auto-rows-auto grid-cols-[auto_minmax(0,1fr)] items-start gap-x-3 py-1">
      <div className="from-primary to-primary/70 text-primary-foreground col-start-1 row-span-2 flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br text-xs font-semibold shadow-sm">
        AI
      </div>
      <div className="text-foreground col-start-2 min-w-0 max-w-[80%] break-words">
        <MessagePrimitive.If assistant>
          <MessageErrorContent />
        </MessagePrimitive.If>

        {/* 时间戳：行末对齐 */}
        <div className="text-muted-foreground/80 mt-1 flex items-center gap-2">
          <MessageTimestamp date={createdAt} />
          {isRunning && (
            <span className="text-muted-foreground inline-flex items-center gap-1 text-[10px]">
              <Loader2 className="h-3 w-3 animate-spin" />
              生成中…
            </span>
          )}
        </div>
      </div>

      {/* 操作行：复制 / 重新生成 / 反馈 */}
      <div className="col-start-2 mt-1.5 flex items-center gap-0.5 opacity-0 transition-opacity group-hover/assist:opacity-100">
        <MessagePrimitive.If assistant>
          <AssistantActions />
        </MessagePrimitive.If>
      </div>
    </MessagePrimitive.Root>
  );
};

/**
 * 错误消息：从 useMessage 读 status 判定
 *
 * chat-controller 写入错误消息时 status 是 { type: 'incomplete', reason: 'error' }。
 */
const MessageErrorContent: FC = () => {
  const isError = useMessage((s): boolean => {
    const st = s.status;
    return st?.type === 'incomplete' && 'reason' in st && st.reason === 'error';
  });
  return (
    <div
      className={cn(
        'rounded-md',
        isError &&
          'border-destructive/40 bg-destructive/5 text-destructive border px-3 py-2',
      )}
      data-error={isError ? 'true' : undefined}
    >
      <MessageParts text tools />
    </div>
  );
};

const AssistantActions: FC = () => {
  const [copied, setCopied] = useState(false);
  const [feedback, setFeedback] = useState<'positive' | 'negative' | null>(null);

  // 重置 feedback（消息变化时）
  useEffect(() => {
    setCopied(false);
    setFeedback(null);
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

      <div className="mx-1 h-3 w-px bg-border" />

      <FeedbackButton
        kind="positive"
        active={feedback === 'positive'}
        onActivate={() => setFeedback((v) => (v === 'positive' ? null : 'positive'))}
      />
      <FeedbackButton
        kind="negative"
        active={feedback === 'negative'}
        onActivate={() => setFeedback((v) => (v === 'negative' ? null : 'negative'))}
      />
    </div>
  );
};

function FeedbackButton({
  kind,
  active,
  onActivate,
}: {
  kind: 'positive' | 'negative';
  active: boolean;
  onActivate: () => void;
}) {
  const Icon = kind === 'positive' ? ThumbsUp : ThumbsDown;
  const Component =
    kind === 'positive'
      ? ActionBarPrimitive.FeedbackPositive
      : ActionBarPrimitive.FeedbackNegative;
  return (
    <Component
      className={cn(
        'inline-flex h-7 w-7 items-center justify-center rounded transition-colors',
        active
          ? 'bg-primary/10 text-primary'
          : 'text-muted-foreground hover:bg-muted hover:text-foreground',
      )}
      title={kind === 'positive' ? '赞' : '踩'}
      onClick={onActivate}
    >
      <Icon size={12} />
    </Component>
  );
}

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

/** 在 running 时显示在 Composer 上方的小提示 */
const ComposerRunningBanner: FC = () => {
  const isRunning = useThread((s) => s.isRunning);
  if (!isRunning) return null;
  return (
    <div className="text-muted-foreground mx-auto mb-1.5 flex w-full max-w-2xl items-center gap-2 px-1 text-[11px]">
      <Loader2 className="h-3 w-3 animate-spin" />
      <span>正在生成回复…</span>
      <span className="text-muted-foreground/60">（可点击下方 ⏹ 停止）</span>
    </div>
  );
};

const Composer: FC = () => (
  <>
    <ComposerRunningBanner />
    <ComposerPrimitive.Root className="bg-background border-border focus-within:border-ring/50 shadow-sm hover:shadow-md mx-auto flex w-full max-w-2xl flex-col rounded-2xl border p-2 transition-all">
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
