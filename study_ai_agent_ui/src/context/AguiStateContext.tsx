/**
 * AG-UI 状态共享 Context —— 精简版
 *
 * 早期版本这里还存 ``state`` 快照给右侧 StatePanel 用。现在改造为：
 *   - 状态（plan / review / citations / code_changes / final_answer）改为
 *     **绑到每条 assistant message 的 ``metadata.custom.state``** 上
 *     （见 :func:`useChatController`），每条消息拥有自己的 state；
 *   - 本 context 只剩两个用途：``currentStage``（被 ``ComposerRunningBanner``
 *     实时读取，stage 切换时 spinner 跟着变）。
 *
 * 这样切到多轮对话时，不同轮次的 plan / review 互不串扰；执行过程
 * 也直接出现在对应那条 AI 消息里（见 ``MessageExecutionState``），不需要
 * 再开一个侧栏。
 */
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
} from 'react';
import type { ReactNode } from 'react';

interface AguiStateStore {
  /** 当前正在执行的阶段（来自 STEP_STARTED） */
  currentStage: string | undefined;
  /** 写入当前阶段；传 undefined 表示阶段结束 */
  setCurrentStage: (stage: string | undefined) => void;
}

const AguiStateContext = createContext<AguiStateStore | undefined>(undefined);

export function AguiStateProvider({ children }: { children: ReactNode }) {
  const [currentStage, setCurrentStageRaw] = useState<string | undefined>(undefined);

  const setCurrentStage = useCallback((stage: string | undefined) => {
    setCurrentStageRaw(stage);
  }, []);

  const value = useMemo<AguiStateStore>(
    () => ({ currentStage, setCurrentStage }),
    [currentStage, setCurrentStage],
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
