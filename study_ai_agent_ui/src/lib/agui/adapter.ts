/**
 * AG-UI 后端 ↔ assistant-ui 的 ChatModelAdapter 桥接（兼容旧 API）
 *
 * 内部委托给 :func:`runAguiAgent`。本文件仅保留作为 ``useLocalRuntime`` 兼容
 * 路径；新的多会话实现请使用 :func:`useChatController`。
 */
import type {
  ChatModelAdapter,
  ChatModelRunOptions,
  ChatModelRunResult,
} from '@assistant-ui/react';
import type { TextMessagePart, ToolCallMessagePart } from '@assistant-ui/react';
import type { ReadonlyJSONValue } from 'assistant-stream/utils';

import { runAguiAgent, runResultToContent } from './run';
import type { AguiAdapterOptions } from './types';

export type { AguiAdapterOptions } from './types';

export { runAguiAgent };

function toAguiMessages(messages: ChatModelRunOptions['messages']): { id: string; role: 'user' | 'assistant' | 'system' | 'tool'; content: string }[] {
  return messages.map((m) => {
    const text = m.content
      .filter((p): p is TextMessagePart => p.type === 'text')
      .map((p) => p.text)
      .join('');
    return {
      id: m.id,
      role: m.role as 'user' | 'assistant' | 'system' | 'tool',
      content: text,
    };
  });
}

export function createAguiAdapter(opts: AguiAdapterOptions): ChatModelAdapter {
  return {
    async run(runOptions): Promise<ChatModelRunResult> {
      const { messages, abortSignal } = runOptions;
      const skill = opts.getSkill();
      const threadId = opts.getThreadId();

      const result = await runAguiAgent({
        apiBaseUrl: opts.apiBaseUrl,
        threadId,
        skill,
        history: toAguiMessages(messages),
        abortSignal,
        onDebug: opts.onDebug,
      });

      if (result.finalState) {
        opts.onState?.(result.finalState);
      }

      const content: Array<TextMessagePart | ToolCallMessagePart> = runResultToContent(
        result,
      ) as Array<TextMessagePart | ToolCallMessagePart>;

      const metadata: ChatModelRunResult['metadata'] = {
        custom: {
          aguiThreadId: threadId,
          aguiSkill: skill,
        },
        ...(result.finalState
          ? { unstable_state: result.finalState as unknown as ReadonlyJSONValue }
          : null),
      };

      return { content, metadata };
    },
  };
}
