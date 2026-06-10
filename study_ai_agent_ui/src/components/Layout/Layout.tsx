/**
 * 全局 Layout
 *
 * - 侧边栏（导航 + 骨架选择 + 历史会话列表）
 * - 顶栏（页面标题 / Skill / 新建 / 主题切换 / 设置）
 * - 主区：children
 */
import { useCallback, useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  AlertCircle,
  Code2,
  Compass,
  Loader2,
  MessageSquare,
  Settings,
  Sparkles,
} from 'lucide-react';

import { Topbar } from './Topbar';
import { HistorySidebar } from '@/components/History';
import { useConfig, useSession, useSkill } from '@/context';
import type { Skeleton } from '@/features/skills';
import { useKeyboardShortcuts } from '@/hooks';
import { cn } from '@/lib/utils';

const NAV_ITEMS = [
  { path: '/chat', label: 'AI 助手', icon: MessageSquare },
  { path: '/config', label: '系统配置', icon: Settings },
] as const;

export interface LayoutProps {
  children: ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [historyCollapsed, setHistoryCollapsed] = useState(false);
  const { config } = useConfig();
  const skill = useSkill();
  const session = useSession();

  // 首次进入应用时若没有任何会话，自动建一个空会话
  useEffect(() => {
    if (session.sessions.length === 0 && !session.activeId) {
      session.createNew(skill.currentSkill);
    }
    // 只在挂载时执行一次（+ 配置变化时）
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleNavClick = useCallback(
    (path: string) => {
      navigate(path);
      setMobileMenuOpen(false);
    },
    [navigate],
  );

  const handleSkillClick = useCallback(
    (id: string) => {
      // 切换 skill 时：
      //   - 如果当前会话已有消息，新建一个空会话（避免上下文混淆）
      //   - 如果当前会话还是空的，只更新它的 skillId 标记
      if (id === skill.currentSkill) {
        setMobileMenuOpen(false);
        return;
      }
      const currentSession = session.sessions.find((s) => s.id === session.activeId);
      const isEmpty = !currentSession || currentSession.messageCount === 0;
      if (isEmpty && currentSession) {
        // 复用空会话 —— 更新元数据即可，title 保留"新会话"
        // SessionContext 暂未提供 updateSkill，这里走 createNew 拿新 id 会更干净
        session.createNew(id);
      } else {
        session.createNew(id);
      }
      skill.setSkill(id);
      setMobileMenuOpen(false);
    },
    [skill, session],
  );

  const currentNav = NAV_ITEMS.find((item) => item.path === location.pathname);

  // 全局快捷键：⌘/Ctrl+K 新建会话
  useKeyboardShortcuts({
    onNewChat: () => session.createNew(skill.currentSkill),
  });

  return (
    <div className="bg-background text-foreground flex h-screen w-screen overflow-hidden">
      {/* ===== 侧边栏（导航 + 智能体） ===== */}
      <aside
        className={cn(
          'bg-card border-border flex shrink-0 flex-col border-r transition-all duration-200',
          'md:relative md:translate-x-0',
          'fixed inset-y-0 left-0 z-50 md:static',
          sidebarCollapsed ? 'md:w-0 md:overflow-hidden md:border-r-0' : 'w-60',
          mobileMenuOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0',
        )}
      >
        {/* 品牌区 */}
        <div className="border-border flex h-14 items-center gap-2.5 border-b px-4">
          <div className="bg-primary text-primary-foreground flex h-8 w-8 items-center justify-center rounded-md">
            <Sparkles size={16} />
          </div>
          <span className="text-base font-bold tracking-tight">Study AI Agent</span>
        </div>

        {/* 导航 */}
        <div className="border-border flex shrink-0 flex-col gap-0.5 border-b p-2">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.path;
            return (
              <button
                key={item.path}
                className={cn(
                  'flex w-full items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors',
                  isActive
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                )}
                onClick={() => handleNavClick(item.path)}
                title={item.label}
              >
                <Icon size={16} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </div>

        {/* 智能体选择器 */}
        <div className="flex flex-1 flex-col gap-1 overflow-y-auto p-2">
          <div className="text-muted-foreground px-2 py-1.5 text-xs font-semibold tracking-wider uppercase">
            智能体
          </div>
          <SkeletonList
            skeletons={skill.skeletons}
            loading={skill.loading}
            error={skill.error}
            currentId={skill.currentSkill}
            onSelect={handleSkillClick}
          />
        </div>

        {/* 底部连接信息 */}
        <div className="border-border shrink-0 border-t p-3 text-xs">
          <div className="text-muted-foreground">后端</div>
          <div className="text-foreground truncate font-mono text-[11px]">
            {config.apiBaseUrl}
          </div>
        </div>
      </aside>

      {/* 移动端遮罩 */}
      {mobileMenuOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/30 md:hidden"
          onClick={() => setMobileMenuOpen(false)}
        />
      )}

      {/* ===== 历史会话侧边栏 ===== */}
      {location.pathname !== '/config' && (
        <HistorySidebar
          collapsed={historyCollapsed}
          onToggleCollapsed={() => setHistoryCollapsed((v) => !v)}
          className="hidden md:flex"
        />
      )}

      {/* ===== 主内容区 ===== */}
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <Topbar
          sidebarCollapsed={sidebarCollapsed}
          onToggleSidebar={() => setSidebarCollapsed((v) => !v)}
          mobileMenuOpen={mobileMenuOpen}
          onToggleMobileMenu={() => setMobileMenuOpen((v) => !v)}
          pageTitle={currentNav?.label ?? 'AI 助手'}
          onNewChat={() => session.createNew(skill.currentSkill)}
          onToggleHistory={() => setHistoryCollapsed((v) => !v)}
          historyCollapsed={historyCollapsed}
        />

        <main className="flex-1 overflow-hidden">{children}</main>
      </div>
    </div>
  );
}

// ---- 子组件 ------------------------------------------------------------

interface SkeletonListProps {
  skeletons: Skeleton[];
  loading: boolean;
  error: string | null;
  currentId: string;
  onSelect: (id: string) => void;
}

function SkeletonList({ skeletons, loading, error, currentId, onSelect }: SkeletonListProps) {
  if (loading) {
    return (
      <div className="text-muted-foreground flex items-center gap-2 px-2 py-1.5 text-xs">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        加载智能体中...
      </div>
    );
  }
  if (error) {
    return (
      <div className="text-destructive flex flex-col gap-1 px-2 py-1.5 text-xs">
        <span className="flex items-center gap-1.5">
          <AlertCircle className="h-3.5 w-3.5" />
          加载失败
        </span>
        <span className="text-muted-foreground text-[10px] leading-relaxed">
          {error}
          <br />
          请检查后端连接，或到 /config 调整地址。
        </span>
      </div>
    );
  }
  if (skeletons.length === 0) {
    return (
      <div className="text-muted-foreground px-2 py-1.5 text-xs">（后端未注册任何智能体）</div>
    );
  }
  return (
    <>
      {skeletons.map((sk) => {
        const isActive = sk.id === currentId;
        const Icon = iconForSkeleton(sk.id);
        return (
          <button
            key={sk.id}
            onClick={() => onSelect(sk.id)}
            className={cn(
              'flex w-full flex-col gap-0.5 rounded-md px-2.5 py-2 text-left transition-colors',
              isActive ? 'bg-accent text-accent-foreground' : 'hover:bg-muted text-foreground',
            )}
            title={sk.description}
          >
            <span className="flex items-center gap-2 text-sm font-medium">
              <Icon size={14} />
              {sk.name}
            </span>
            <span
              className={cn(
                'line-clamp-2 text-[11px] leading-snug',
                isActive ? 'text-accent-foreground/80' : 'text-muted-foreground',
              )}
            >
              {sk.description}
            </span>
            <span className="text-muted-foreground mt-0.5 text-[10px]">
              {sk.tool_count} 工具
              {Object.keys(sk.hitl_rules).length > 0
                ? ` · ${Object.keys(sk.hitl_rules).length} 需审批`
                : ''}
            </span>
          </button>
        );
      })}
    </>
  );
}

function iconForSkeleton(id: string | undefined): typeof Code2 {
  switch (id) {
    case 'coding':
      return Code2;
    case 'research':
      return Compass;
    default:
      return Sparkles;
  }
}
