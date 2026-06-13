/**
 * 顶栏
 *
 * - 移动端菜单按钮
 * - 当前页面 / Skill 快速切换 / 新建会话
 * - 主题切换（明/暗）
 * - 系统配置入口
 * - 历史侧边栏折叠
 */
import { useCallback, useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Check,
  ChevronDown,
  History,
  Loader2,
  Menu,
  Moon,
  PanelLeft,
  Plus,
  Settings,
  Sparkles,
  Sun,
  X,
} from 'lucide-react';

import { useSkill } from '@/context';
import { useTheme } from '@/hooks';
import { Button } from '@/components/assistant-ui';
import { cn } from '@/lib/utils';

export interface TopbarProps {
  /** 侧边栏折叠状态（受控） */
  sidebarCollapsed: boolean;
  onToggleSidebar: () => void;
  /** 历史侧边栏折叠状态（受控） */
  historyCollapsed: boolean;
  onToggleHistory: () => void;
  /** 移动端菜单 */
  mobileMenuOpen: boolean;
  onToggleMobileMenu: () => void;
  /** 当前页面标题 */
  pageTitle: string;
  /** 新建会话回调（用于在 Chat 页面触发 assistant-ui 的新线程） */
  onNewChat?: () => void;
  /**
   * 切换智能体的回调（用于顶部面包屑）
   *
   * 与 ``Layout`` 里侧边栏的 handler 行为一致：先建一个新会话，
   * 再把当前 skill 切到目标 id。早期版本只调用 ``skill.setSkill``，
   * 结果点击后顶栏名字变了，但消息历史还属于旧 agent，体感像"切换无效"。
   */
  onSelectSkill?: (id: string) => void;
}

export function Topbar({
  sidebarCollapsed,
  onToggleSidebar,
  historyCollapsed,
  onToggleHistory,
  mobileMenuOpen,
  onToggleMobileMenu,
  pageTitle,
  onNewChat,
  onSelectSkill,
}: TopbarProps) {
  const skill = useSkill();
  const { theme, setTheme } = useTheme();
  const navigate = useNavigate();

  return (
    <header
      className={cn(
        'border-border bg-background/80 flex h-14 shrink-0 items-center justify-between gap-2 border-b px-3 backdrop-blur sm:gap-3 md:px-5',
      )}
    >
      <div className="flex min-w-0 flex-1 items-center gap-2">
        {/* 桌面端：折叠侧边栏按钮 */}
        <button
          className="text-muted-foreground hover:bg-muted hover:text-foreground hidden h-9 w-9 shrink-0 items-center justify-center rounded-md transition-colors md:inline-flex"
          onClick={onToggleSidebar}
          title={sidebarCollapsed ? '展开侧边栏' : '收起侧边栏'}
          aria-label="切换左侧导航"
        >
          <PanelLeft size={18} />
        </button>

        {/* 移动端：菜单按钮 */}
        <button
          className="text-muted-foreground hover:bg-muted hover:text-foreground inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-md transition-colors md:hidden"
          onClick={onToggleMobileMenu}
          aria-label="打开导航菜单"
        >
          {mobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
        </button>

        <div className="flex min-w-0 items-center gap-2 text-sm">
          <span className="text-muted-foreground hidden sm:inline">{pageTitle}</span>
          <span className="text-border hidden sm:inline">/</span>
          <SkillSwitcher
            currentId={skill.currentSkill}
            currentName={skill.current?.name ?? skill.currentSkill}
            loading={skill.loading && !skill.current}
            // 切智能体的实际行为由 Layout 注入（建新会话 + 切 skill）；
            // 注入逻辑在的话，走注入；没有就回退到 skill.setSkill。
            onSelect={onSelectSkill ?? skill.setSkill}
          />
        </div>
      </div>

      <div className="flex shrink-0 items-center gap-1">
        {onNewChat && (
          <Button
            variant="ghost"
            size="sm"
            onClick={onNewChat}
            title="新建会话 (Ctrl/⌘+K)"
            aria-label="新建会话"
            className="px-2 sm:px-3"
          >
            <Plus size={16} />
            <span className="hidden sm:inline">新会话</span>
          </Button>
        )}

        {/* 历史侧边栏折叠 / 移动端抽屉 */}
        <button
          className={cn(
            'hover:bg-muted inline-flex h-9 w-9 items-center justify-center rounded-md transition-colors',
            historyCollapsed
              ? 'text-muted-foreground hover:text-foreground'
              : 'bg-muted text-foreground',
          )}
          onClick={onToggleHistory}
          title={historyCollapsed ? '展开历史' : '收起历史'}
          aria-label="切换历史会话"
        >
          <History size={18} />
        </button>

        {/* 主题切换 */}
        <button
          className="text-muted-foreground hover:bg-muted hover:text-foreground inline-flex h-9 w-9 items-center justify-center rounded-md transition-colors"
          onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
          title={theme === 'dark' ? '切换到浅色' : '切换到深色'}
          aria-label="切换主题"
        >
          {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
        </button>

        <button
          className="text-muted-foreground hover:bg-muted hover:text-foreground inline-flex h-9 w-9 items-center justify-center rounded-md transition-colors"
          onClick={() => navigate('/config')}
          title="系统配置"
          aria-label="系统配置"
        >
          <Settings size={18} />
        </button>
      </div>
    </header>
  );
}

/* ===========================
   Skill 快速切换下拉
   =========================== */

interface SkillSwitcherProps {
  currentId: string;
  currentName: string;
  loading: boolean;
  onSelect: (id: string) => void;
}

function SkillSwitcher({ currentId, currentName, loading, onSelect }: SkillSwitcherProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const skill = useSkill();

  useEffect(() => {
    if (!open) return;
    const handleClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [open]);

  const handleSelect = useCallback(
    (id: string) => {
      onSelect(id);
      setOpen(false);
    },
    [onSelect],
  );

  return (
    <div className="relative min-w-0" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className={cn(
          'text-foreground hover:bg-muted inline-flex h-8 max-w-[140px] items-center gap-1.5 rounded-md px-2 text-sm font-medium transition-colors sm:max-w-[200px]',
          open && 'bg-muted',
        )}
      >
        {loading ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin shrink-0" />
        ) : (
          <Sparkles className="h-3.5 w-3.5 shrink-0" />
        )}
        <span className="truncate">{currentName}</span>
        <ChevronDown
          className={cn(
            'h-3.5 w-3.5 shrink-0 opacity-60 transition-transform',
            open && 'rotate-180',
          )}
        />
      </button>

      {open && (
        <div className="bg-popover text-popover-foreground border-border absolute left-0 top-full z-50 mt-1.5 w-64 max-w-[calc(100vw-1.5rem)] rounded-lg border p-1 shadow-lg sm:w-72">
          <div className="text-muted-foreground px-2 py-1.5 text-xs font-semibold tracking-wider uppercase">
            切换智能体
          </div>
          {skill.skeletons.length === 0 && !skill.loading && (
            <div className="text-muted-foreground px-2 py-1.5 text-xs">
              （后端未注册任何智能体）
            </div>
          )}
          {skill.skeletons.map((sk) => {
            const isActive = sk.id === currentId;
            return (
              <button
                key={sk.id}
                type="button"
                onClick={() => handleSelect(sk.id)}
                className={cn(
                  'flex w-full items-start gap-2 rounded-md px-2 py-1.5 text-left transition-colors',
                  isActive ? 'bg-accent' : 'hover:bg-muted',
                )}
              >
                <Sparkles className="text-muted-foreground mt-0.5 h-3.5 w-3.5 shrink-0" />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5 text-sm font-medium">
                    <span className="truncate">{sk.name}</span>
                    {isActive && <Check className="text-primary h-3.5 w-3.5 shrink-0" />}
                  </div>
                  <div className="text-muted-foreground mt-0.5 line-clamp-1 text-[11px]">
                    {sk.description}
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
