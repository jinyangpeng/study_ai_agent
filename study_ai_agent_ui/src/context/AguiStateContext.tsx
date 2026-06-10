/**
 * AG-UI 状态共享 Context
 *
 * 后端通过 ``STATE_SNAPSHOT`` 事件推送的 plan / review / citations / code_changes
 * 会经由 :func:`useChatController` 写入这里的 store。聊天页面再通过
 * ``useAguiState`` 拿到最新状态，渲染到右侧状态面板中。
 *
 * 为什么不直接用 assistant-ui 的 ``metadata.unstable_state``：
 *   1. 那个字段会绑定到某一条消息上、生命周期跟 message 走；
 *   2. 跨消息累积状态（plan → review → final_answer）不方便；
 *   3. 在独立面板中显示需要重新订阅。
 * 因此用这个独立的 React context。
 */
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
} from 'react';
import type { ReactNode } from 'react';

import type { AguiStateSnapshot } from '@/lib/agui';

interface AguiStateStore {
  /** 最新的 state 快照 */
  state: AguiStateSnapshot;
  /** 写入最新快照 */
  setState: (next: AguiStateSnapshot) => void;
  /** 局部更新（不会清空已有字段） */
  patchState: (patch: Partial<AguiStateSnapshot>) => void;
  /** 清空 state（新会话时调用） */
  resetState: () => void;
  /** 监听 setState 变化的订阅 id 集合（调试用） */
  version: number;
}

const AguiStateContext = createContext<AguiStateStore | undefined>(undefined);

export function AguiStateProvider({ children }: { children: ReactNode }) {
  const [state, setStateRaw] = useState<AguiStateSnapshot>({});
  const [version, setVersion] = useState(0);
  const lastStateRef = useRef<AguiStateSnapshot>({});

  const setState = useCallback((next: AguiStateSnapshot) => {
    lastStateRef.current = next;
    setStateRaw(next);
    setVersion((v) => v + 1);
  }, []);

  const patchState = useCallback((patch: Partial<AguiStateSnapshot>) => {
    const next = { ...lastStateRef.current, ...patch };
    lastStateRef.current = next;
    setStateRaw(next);
    setVersion((v) => v + 1);
  }, []);

  const resetState = useCallback(() => {
    lastStateRef.current = {};
    setStateRaw({});
    setVersion((v) => v + 1);
  }, []);

  const value = useMemo<AguiStateStore>(
    () => ({ state, setState, patchState, resetState, version }),
    [state, setState, patchState, resetState, version],
  );

  return <AguiStateContext.Provider value={value}>{children}</AguiStateContext.Provider>;
}

export function useAguiState(): AguiStateStore {
  const ctx = useContext(AguiStateContext);
  if (!ctx) {
    throw new Error('useAguiState must be used within an AguiStateProvider');
  }
  return ctx;
}
