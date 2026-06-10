import type { ReactNode } from 'react';
import { ErrorBoundary } from '@/components';
import {
  AguiStateProvider,
  ConfigProvider,
  SessionProvider,
  SkillProvider,
} from '@/context';

export function AppProviders({ children }: { children: ReactNode }) {
  return (
    <ErrorBoundary>
      <ConfigProvider>
        {/* SessionProvider 独立持有 localStorage 中的会话列表 */}
        <SessionProvider>
          {/* SkillProvider 依赖 ConfigProvider 里的 apiBaseUrl / defaultSkill */}
          <SkillProvider>
            {/* AguiStateProvider 收集 STATE_SNAPSHOT 事件，写入独立 store */}
            <AguiStateProvider>{children}</AguiStateProvider>
          </SkillProvider>
        </SessionProvider>
      </ConfigProvider>
    </ErrorBoundary>
  );
}
