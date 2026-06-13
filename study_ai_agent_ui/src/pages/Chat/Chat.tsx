/**
 * 聊天页面
 *
 * - 使用自定义 :func:`useChatController` 渲染消息流
 *   （基于 assistant-ui 的 ``useExternalStoreRuntime``，支持多会话）
 * - 执行状态（plan / review / code_changes / citations）由每条 AI 消息
 *   自带的 ``MessageExecutionState`` 内联展示（见
 *   :file:`assistant-ui/message-execution-state.tsx`），不再使用右侧面板。
 * - 通过 ``ErrorToast`` 在聊天区顶部展示流式 run 中的错误提示
 */
import { AssistantRuntimeProvider } from '@assistant-ui/react';
import { useCallback, useEffect, useMemo, useState } from 'react';

import { ErrorToast, Thread } from '@/components/assistant-ui';
import { useChatController } from '@/lib/agui';
import { useAguiState } from '@/context';

export default function Chat() {
  const { setCurrentStage } = useAguiState();
  const [chatError, setChatError] = useState<Error | null>(null);

  // 错误来了：1) 显示顶部 toast；2) 通过 onError 把错误冒泡到 controller
  const onError = useCallback((err: Error) => {
    setChatError(err);
  }, []);

  // 用 useMemo 包一层避免 options 引用频繁变化导致 controller 重建
  const options = useMemo(() => ({ onError }), [onError]);
  const { runtime, activeId } = useChatController(options);

  // 切换会话时清空错误 + 重置当前 stage（避免 banner 残留上轮文案）
  useEffect(() => {
    setChatError(null);
    setCurrentStage(undefined);
    // 只依赖 activeId，避免 setCurrentStage 变化时无限循环
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeId]);

  return (
    <div className="flex h-full w-full overflow-hidden">
      <div className="bg-background relative flex h-full flex-1 flex-col overflow-hidden">
        <AssistantRuntimeProvider runtime={runtime}>
          {/* 错误 toast 放在 Thread 上方 —— 不参与消息流，单独浮层 */}
          <div className="sticky top-0 z-10 pt-2">
            <ErrorToast
              error={chatError}
              onDismiss={() => setChatError(null)}
              autoDismissMs={8000}
            />
          </div>
          <Thread className="flex-1" />
        </AssistantRuntimeProvider>
      </div>
    </div>
  );
}
