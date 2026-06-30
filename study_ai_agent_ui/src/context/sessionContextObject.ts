/**
 * 单独的 SessionContext 容器（拆出来让 SessionContext.tsx 只 export 组件，
 * 以满足 ``react-refresh/only-export-components``）。
 */
import { createContext } from 'react';
import type { SessionContextValue } from './SessionContext';

export const SessionContext = createContext<SessionContextValue | undefined>(undefined);
