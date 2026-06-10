import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import type { AppConfig } from '@/types';
import { DEFAULT_CONFIG, clearConfig, loadConfig, saveConfig } from '@/features/config';

interface ConfigContextValue {
  config: AppConfig;
  setConfig: (patch: Partial<AppConfig>) => void;
  resetConfig: () => void;
}

const ConfigContext = createContext<ConfigContextValue | undefined>(undefined);

export function ConfigProvider({ children }: { children: ReactNode }) {
  const [config, setConfigState] = useState<AppConfig>(() => loadConfig());

  useEffect(() => {
    saveConfig(config);
  }, [config]);

  const setConfig = useCallback((patch: Partial<AppConfig>) => {
    setConfigState((prev) => ({ ...prev, ...patch }));
  }, []);

  const resetConfig = useCallback(() => {
    clearConfig();
    setConfigState({ ...DEFAULT_CONFIG });
  }, []);

  return (
    <ConfigContext.Provider value={{ config, setConfig, resetConfig }}>
      {children}
    </ConfigContext.Provider>
  );
}

export function useConfig(): ConfigContextValue {
  const ctx = useContext(ConfigContext);
  if (!ctx) {
    throw new Error('useConfig must be used within a ConfigProvider');
  }
  return ctx;
}
