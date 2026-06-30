/**
 * 历史会话侧边栏
 *
 * 展示 SessionContext 中的全部会话，支持：
 *   - 点击切换
 *   - 新建会话
 *   - 删除会话（hover 直接出现删除按钮 — dogfood ISSUE-005 修复）
 *   - 按日期分组（今天 / 昨天 / 本周 / 更早）
 *   - 搜索关键字
 *   - 显示当前 skill 图标
 *   - 双击会话标题进入内联重命名
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Check,
  MessageSquarePlus,
  Pencil,
  Search,
  Trash2,
  X,
  Sparkles,
  Code2,
  Compass,
  HelpCircle,
} from 'lucide-react';

import { useSession, useSkill } from '@/context';
import type { SessionMeta } from '@/features/sessions';
import { Button } from '@/components/assistant-ui';
import { cn } from '@/lib/utils';

export interface HistorySidebarProps {
  /** 折叠状态（受控） */
  collapsed: boolean;
  /** 折叠切换回调 */
  onToggleCollapsed?: () => void;
  /** 移动端是否打开（受控） */
  mobileOpen?: boolean;
  /** 移动端关闭回调 */
  onMobileClose?: () => void;
  className?: string;
}

export function HistorySidebar({
  collapsed,
  mobileOpen = false,
  onMobileClose,
  className,
}: HistorySidebarProps) {
  const session = useSession();
  const skill = useSkill();
  const [query, setQuery] = useState('');

  const filtered = useMemo(() => {
    if (!query.trim()) return session.sessions;
    const q = query.trim().toLowerCase();
    return session.sessions.filter((s) => s.title.toLowerCase().includes(q));
  }, [session.sessions, query]);

  const grouped = useMemo(() => groupByDate(filtered), [filtered]);

  // 移动端打开时禁止 body 滚动
  useEffect(() => {
    if (!mobileOpen) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = prev;
    };
  }, [mobileOpen]);

  return (
    <aside
      className={cn(
        'border-border bg-card text-card-foreground flex shrink-0 flex-col border-r transition-all duration-200',
        // 桌面端：宽度受 collapsed 控制
        'md:relative md:translate-x-0',
        collapsed ? 'md:w-0 md:overflow-hidden md:border-r-0' : 'md:w-64',
        // 移动端：固定在左侧、z-40，正常态滑出，open 时滑入
        'fixed inset-y-0 left-0 z-40 w-72 max-w-[85vw] md:static',
        mobileOpen ? 'translate-x-0 shadow-2xl' : '-translate-x-full md:translate-x-0',
        className,
      )}
    >
      <div className="flex shrink-0 items-center justify-between gap-2 px-3 py-2.5">
        <div className="flex items-center gap-1.5 text-sm font-semibold">
          <span>历史会话</span>
          <span className="text-muted-foreground text-xs">({session.sessions.length})</span>
        </div>
        {/* 移动端：关闭按钮（桌面端不显示） */}
        <button
          type="button"
          className="text-muted-foreground hover:bg-muted hover:text-foreground inline-flex h-7 w-7 items-center justify-center rounded-md transition-colors md:hidden"
          onClick={onMobileClose}
          title="关闭"
          aria-label="关闭历史会话列表"
        >
          <X size={14} />
        </button>
      </div>

      {/* 新建 + 搜索 */}
      <div className="flex shrink-0 flex-col gap-2 px-2 pb-2">
        <Button
          variant="default"
          size="sm"
          className="w-full justify-start"
          onClick={() => session.createNew(skill.currentSkill)}
        >
          <MessageSquarePlus size={14} />
          <span>新建会话</span>
          <span className="text-primary-foreground/60 ml-auto text-[10px]">⌘K</span>
        </Button>
        <div className="border-border bg-background flex items-center gap-1.5 rounded-md border px-2 py-1">
          <Search className="text-muted-foreground h-3.5 w-3.5 shrink-0" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="搜索会话…"
            className="placeholder:text-muted-foreground text-foreground w-full bg-transparent text-xs outline-none"
          />
          {query && (
            <button
              type="button"
              className="text-muted-foreground hover:text-foreground"
              onClick={() => setQuery('')}
              title="清空"
            >
              <X size={12} />
            </button>
          )}
        </div>
      </div>

      {/* 列表 */}
      <div className="flex-1 overflow-y-auto px-1.5 pb-2">
        {session.sessions.length === 0 ? (
          <EmptyState />
        ) : (
          (Object.entries(grouped) as [BucketKey, SessionMeta[]][]).map(([bucket, items]) => (
            <div key={bucket} className="mb-1">
              <div className="text-muted-foreground sticky top-0 z-10 bg-card/80 px-2 py-1.5 text-[10px] font-semibold tracking-wider uppercase backdrop-blur">
                {bucket}
              </div>
              <ul className="flex flex-col gap-0.5">
                {items.map((s) => (
                  <SessionItem
                    key={s.id}
                    sessionMeta={s}
                    active={s.id === session.activeId}
                    onClick={() => {
                      session.switchTo(s.id);
                      onMobileClose?.();
                    }}
                    onDelete={() => session.remove(s.id)}
                    onRename={(title) => session.rename(s.id, title)}
                  />
                ))}
              </ul>
            </div>
          ))
        )}
        {session.sessions.length > 0 && filtered.length === 0 && (
          <div className="text-muted-foreground px-2 py-4 text-center text-xs">无匹配会话</div>
        )}
      </div>
    </aside>
  );
}

// ---- 子组件 ---------------------------------------------------------------

function SessionItem({
  sessionMeta,
  active,
  onClick,
  onDelete,
  onRename,
}: {
  sessionMeta: SessionMeta;
  active: boolean;
  onClick: () => void;
  onDelete: () => void;
  onRename: (title: string) => void;
}) {
  const [hover, setHover] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draftTitle, setDraftTitle] = useState(sessionMeta.title);
  const ref = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (editing) {
      inputRef.current?.focus();
      inputRef.current?.select();
    }
  }, [editing]);

  const Icon = iconForSkill(sessionMeta.skillId);

  const commitRename = () => {
    const t = draftTitle.trim();
    if (t) onRename(t);
    setEditing(false);
  };

  return (
    <li>
      <div
        ref={ref}
        className={cn(
          'group relative flex cursor-pointer items-center gap-1.5 rounded-md px-2 py-1.5 text-sm transition-colors',
          active ? 'bg-accent text-accent-foreground' : 'hover:bg-muted text-foreground/90',
        )}
        onMouseEnter={() => setHover(true)}
        onMouseLeave={() => setHover(false)}
        onClick={() => !editing && onClick()}
        onDoubleClick={() => {
          setDraftTitle(sessionMeta.title);
          setEditing(true);
        }}
      >
        <Icon className="text-muted-foreground h-3.5 w-3.5 shrink-0" />
        <div className="min-w-0 flex-1">
          {editing ? (
            <input
              ref={inputRef}
              value={draftTitle}
              onChange={(e) => setDraftTitle(e.target.value)}
              onClick={(e) => e.stopPropagation()}
              onKeyDown={(e) => {
                if (e.key === 'Enter') commitRename();
                else if (e.key === 'Escape') setEditing(false);
              }}
              onBlur={commitRename}
              className="bg-background text-foreground w-full rounded border px-1 text-[13px] outline-none"
            />
          ) : (
            <>
              <div className="truncate text-[13px]">{sessionMeta.title}</div>
              <div className="text-muted-foreground flex items-center gap-1 text-[10px]">
                <span>{sessionMeta.messageCount} 条消息</span>
                <span>·</span>
                <span>{formatTime(sessionMeta.updatedAt)}</span>
              </div>
            </>
          )}
        </div>
        {(hover || active) && !editing && (
          <div className="flex items-center">
            <button
              type="button"
              className="text-muted-foreground hover:text-foreground hover:bg-background/60 rounded p-0.5"
              onClick={(e) => {
                e.stopPropagation();
                setDraftTitle(sessionMeta.title);
                setEditing(true);
              }}
              title="重命名"
            >
              <Pencil size={12} />
            </button>
            <button
              type="button"
              className="text-muted-foreground hover:text-destructive hover:bg-destructive/10 rounded p-0.5"
              onClick={(e) => {
                e.stopPropagation();
                onDelete();
              }}
              title="删除"
            >
              <Trash2 size={12} />
            </button>
          </div>
        )}
        {active && !editing && (
          <Check className="text-primary h-3.5 w-3.5 shrink-0" />
        )}
      </div>
    </li>
  );
}

function EmptyState() {
  return (
    <div className="text-muted-foreground flex flex-col items-center justify-center px-4 py-12 text-center">
      <div className="bg-muted mb-2 flex h-10 w-10 items-center justify-center rounded-full">
        <MessageSquarePlus className="h-5 w-5" />
      </div>
      <div className="text-foreground text-sm font-medium">还没有会话</div>
      <div className="mt-1 text-xs">点击"新建会话"或按 ⌘K</div>
    </div>
  );
}

function iconForSkill(id?: string): typeof Code2 {
  switch (id) {
    case 'coding':
      return Code2;
    case 'research':
      return Compass;
    case 'qa':
      return HelpCircle;
    default:
      return Sparkles;
  }
}

// ---- 分组逻辑 -------------------------------------------------------------

type BucketKey = '今天' | '昨天' | '本周' | '更早';

function groupByDate(sessions: SessionMeta[]): Record<BucketKey, SessionMeta[]> {
  const result: Record<BucketKey, SessionMeta[]> = {
    今天: [],
    昨天: [],
    本周: [],
    更早: [],
  };
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const yesterday = today - 86400000;
  const weekAgo = today - 7 * 86400000;

  for (const s of sessions) {
    if (s.updatedAt >= today) result['今天'].push(s);
    else if (s.updatedAt >= yesterday) result['昨天'].push(s);
    else if (s.updatedAt >= weekAgo) result['本周'].push(s);
    else result['更早'].push(s);
  }
  return result;
}

function formatTime(ts: number): string {
  const d = new Date(ts);
  const now = new Date();
  if (d.toDateString() === now.toDateString()) {
    return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

function pad(n: number): string {
  return n < 10 ? `0${n}` : String(n);
}
