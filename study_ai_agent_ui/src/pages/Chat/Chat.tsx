/**
 * 聊天页面
 *
 * - 使用自定义 :func:`useChatController` 渲染消息流
 *   （基于 assistant-ui 的 ``useExternalStoreRuntime``，支持多会话）
 * - 通过 ``useAguiState`` + ``StatePanel`` 在右侧展示 plan / review / citations 等状态
 */
import { AssistantRuntimeProvider } from '@assistant-ui/react';
import { useCallback, useEffect, useMemo } from 'react';

import { StatePanel, Thread } from '@/components/assistant-ui';
import { useChatController } from '@/lib/agui';
import { useAguiState } from '@/context';

export default function Chat() {
  const aguiState = useAguiState();

  // 把后端 STATE_SNAPSHOT 推给右侧面板
  const onState = useCallback(
    (snap: unknown) => aguiState.setState(snap as Parameters<typeof aguiState.setState>[0]),
    [aguiState.setState],
  );

  const onError = useCallback(
    (err: Error) => {
      aguiState.patchState({ final_answer: `⚠️ ${err.message}` });
    },
    [aguiState.patchState],
  );

  // 用 useMemo 包一层避免 options 引用频繁变化导致 controller 重建
  const options = useMemo(() => ({ onState, onError }), [onState, onError]);
  const { runtime, activeId } = useChatController(options);

  // 切换会话时清空右侧状态
  useEffect(() => {
    aguiState.resetState();
    // 只依赖 activeId，避免 aguiState 变化时无限循环
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeId]);

  return (
    <div className="flex h-full w-full overflow-hidden">
      <div className="bg-background relative flex h-full flex-1 flex-col overflow-hidden">
        <AssistantRuntimeProvider runtime={runtime}>
          <Thread className="flex-1" />
        </AssistantRuntimeProvider>
      </div>
      <StatePanel />
    </div>
  );
}
