/**
 * ``useSession`` 单独抽出以满足 ``react-refresh/only-export-components``：
 * SessionContext.tsx 文件只 export React 组件（SessionProvider）时，Vite
 * 的 Fast Refresh 才能保留组件状态；混导出非组件会触发降级。
 */
import { useContext } from 'react';

import { SessionContext } from './sessionContextObject';
import type { SessionContextValue } from './SessionContext';

export function useSession(): SessionContextValue {
  const ctx = useContext(SessionContext);
  if (!ctx) {
    throw new Error('useSession must be used within a SessionProvider');
  }
  return ctx;
}
