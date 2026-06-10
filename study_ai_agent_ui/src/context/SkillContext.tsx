/**
 * 智能体（Skill）Context
 *
 * 设计目标：
 *   - 单一来源的"当前智能体"，Layout 侧栏与 Chat 页面共享
 *   - 自动从后端 ``/skeletons`` 拉取列表；加载失败时使用 ``config.defaultSkill``
 *   - 切换智能体会触发 threadId 重新生成（见 :func:`useChatController`）
 *   - 用户在 /config 选的 defaultSkill 是 *默认值*；实际生效值以前端
 *     拉到的后端列表为准
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import type { ReactNode } from 'react';

import { useConfig } from '@/context/ConfigContext';
import { fetchSkeletons } from '@/features/skills';
import type { Skeleton } from '@/features/skills';

interface SkillContextValue {
  /** 当前选中的 skill id */
  currentSkill: string;
  /** 切换 skill */
  setSkill: (id: string) => void;
  /** 后端已注册的智能体列表（去重按 id 升序） */
  skeletons: Skeleton[];
  /** 加载状态 */
  loading: boolean;
  /** 错误信息 */
  error: string | null;
  /** 当前选中的智能体详情（来自 skeletons 列表） */
  current: Skeleton | null;
}

const SkillContext = createContext<SkillContextValue | undefined>(undefined);

export interface SkillProviderProps {
  children: ReactNode;
}

export function SkillProvider({ children }: SkillProviderProps) {
  const { config } = useConfig();
  const [skeletons, setSkeletons] = useState<Skeleton[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentSkill, setCurrentSkill] = useState<string>(config.defaultSkill);
  const userPickedRef = useRef(false);

  // 配置变化时同步默认智能体（仅当用户没主动选过时）
  useEffect(() => {
    if (!userPickedRef.current) {
      setCurrentSkill(config.defaultSkill);
    }
  }, [config.defaultSkill]);

  // 拉取 /skeletons
  useEffect(() => {
    const ac = new AbortController();
    setLoading(true);
    setError(null);
    fetchSkeletons(config.apiBaseUrl, ac.signal)
      .then((data) => {
        setSkeletons(data.skeletons);
        // 如果当前选中不在后端列表里，回退到后端默认
        setCurrentSkill((prev) => {
          if (data.skeletons.some((s) => s.id === prev)) return prev;
          return data.default;
        });
      })
      .catch((err) => {
        if ((err as Error).name === 'AbortError') return;
        setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => setLoading(false));
    return () => ac.abort();
  }, [config.apiBaseUrl]);

  const setSkill = useCallback((id: string) => {
    userPickedRef.current = true;
    setCurrentSkill(id);
  }, []);

  const value = useMemo<SkillContextValue>(() => {
    const current = skeletons.find((s) => s.id === currentSkill) ?? null;
    return {
      currentSkill,
      setSkill,
      skeletons,
      loading,
      error,
      current,
    };
  }, [currentSkill, setSkill, skeletons, loading, error]);

  return <SkillContext.Provider value={value}>{children}</SkillContext.Provider>;
}

export function useSkill(): SkillContextValue {
  const ctx = useContext(SkillContext);
  if (!ctx) {
    throw new Error('useSkill must be used within a SkillProvider');
  }
  return ctx;
}
