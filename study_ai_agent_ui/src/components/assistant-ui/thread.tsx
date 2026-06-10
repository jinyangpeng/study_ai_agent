/**
 * Thread 组件
 *
 * 封装 assistant-ui 的 ThreadPrimitive 集合，用 Tailwind 做样式。
 * 设计参照 shadcn/ui 官方示例 + AI Studio 风格：渐变欢迎区、quick prompt 卡片、
 * 消息操作行（复制 / 重新生成 / 反馈）。
 */
import { useState, useEffect } from 'react';
import {
  ActionBarPrimitive,
  ComposerPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
} from '@assistant-ui/react';
import {
  ArrowDownIcon,
  Check,
  Copy,
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
  type LucideIcon,
} from 'lucide-react';
import type { FC } from 'react';

import { MarkdownText } from './markdown-text';
import { ToolFallback } from './tool-fallback';
import { Button } from './ui/button';
import { useSkill } from '@/context';
import { cn } from '@/lib/utils';

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
    </ThreadPrimitive.Viewport>

    <div className="sticky bottom-0 mt-auto flex w-full max-w-2xl flex-col items-stretch self-center px-4 pb-4">
      <Composer />
    </div>
  </ThreadPrimitive.Root>
);

// ---- Welcome (empty state) ---------------------------------------------

const ThreadWelcome: FC = () => {
  const skill = useSkill();

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

      {/* Quick prompts */}
      <div className="grid w-full grid-cols-1 gap-3 sm:grid-cols-2">
        <QuickPrompt
          icon={Code2}
          title="编程任务"
          description="写代码、读文件、跑命令"
          prompt="帮我用 Python 实现一个 LRU 缓存，要求有完整的测试用例。"
        />
        <QuickPrompt
          icon={Compass}
          title="研究分析"
          description="搜索、对比、综述"
          prompt="总结 2025 年 LLM Agent 的最新发展趋势，分技术、应用、挑战三部分。"
        />
        <QuickPrompt
          icon={BookOpen}
          title="代码解读"
          description="理解项目结构"
          prompt="请解释当前项目 src/core 目录下的核心模块职责。"
        />
        <QuickPrompt
          icon={Lightbulb}
          title="头脑风暴"
          description="产生新想法"
          prompt="给一个 AI Agent 产品设计 5 个差异化的核心功能。"
        />
      </div>
    </div>
  );
};

function QuickPrompt({
  icon: Icon,
  title,
  description,
  prompt,
}: {
  icon: LucideIcon;
  title: string;
  description: string;
  prompt: string;
}) {
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

// ---- Messages ---------------------------------------------------------

const UserMessage: FC = () => (
  <MessagePrimitive.Root className="group/user relative mb-5 grid w-full max-w-2xl auto-rows-auto grid-cols-[minmax(0,1fr)_auto] items-end gap-x-2 py-1">
    <div className="bg-muted text-foreground col-start-2 max-w-[80%] rounded-2xl rounded-br-md px-4 py-2.5 break-words whitespace-pre-wrap shadow-sm">
      <MessageParts text />
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

const AssistantMessage: FC = () => {
  return (
    <MessagePrimitive.Root className="group/assist relative mb-5 grid w-full max-w-2xl auto-rows-auto grid-cols-[auto_minmax(0,1fr)] items-start gap-x-3 py-1">
      <div className="from-primary to-primary/70 text-primary-foreground col-start-1 row-span-2 flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br text-xs font-semibold shadow-sm">
        AI
      </div>
      <div className="text-foreground col-start-2 max-w-[80%] break-words">
        <MessageParts text tools />
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

const Composer: FC = () => (
  <ComposerPrimitive.Root className="bg-background border-border focus-within:border-ring/50 shadow-sm hover:shadow-md flex w-full flex-col rounded-2xl border p-2 transition-all">
    <ComposerPrimitive.Input
      placeholder="发消息..."
      className="text-foreground placeholder:text-muted-foreground max-h-40 min-h-10 w-full flex-1 resize-none border-none bg-transparent px-3 py-2 text-sm outline-none focus:outline-none"
      rows={1}
    />
    <div className="flex items-center justify-end gap-2 px-1 pt-1">
      <ThreadPrimitive.Empty>
        <ThreadSuggestionRow />
      </ThreadPrimitive.Empty>
      <ComposerAction />
    </div>
  </ComposerPrimitive.Root>
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

export const ThreadScrollToBottom: FC = () => (
  <ThreadPrimitive.ScrollToBottom className="bg-background text-muted-foreground hover:text-foreground inline-flex h-8 w-8 items-center justify-center rounded-full border shadow-sm">
    <ArrowDownIcon className="h-4 w-4" />
  </ThreadPrimitive.ScrollToBottom>
);
