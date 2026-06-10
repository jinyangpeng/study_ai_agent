/**
 * 系统配置页
 *
 * - 维护 API 基础地址 / 默认骨架 / 模拟模式 等运行时配置
 * - 提供"测试连接"按钮（GET /health）
 * - 骨架列表从后端 ``/skeletons`` 拉取
 *
 * 样式使用 Tailwind CSS。
 */
import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AlertCircle,
  CheckCircle2,
  Loader2,
  RotateCcw,
  Save,
  Settings as SettingsIcon,
  Wifi,
} from 'lucide-react';

import { useConfig, useSkill } from '@/context';
import { fetchHealth } from '@/features/config';
import { fetchSkeletons } from '@/features/skills';
import type { Skeleton } from '@/features/skills';
import type { AppConfig } from '@/types';
import { Button } from '@/components/assistant-ui';
import { cn } from '@/lib/utils';

type TestStatus = 'idle' | 'testing' | 'success' | 'error';

export default function Config() {
  const { config, setConfig, resetConfig } = useConfig();
  const { setSkill } = useSkill();
  const navigate = useNavigate();
  const [formData, setFormData] = useState<AppConfig>(config);
  const [saved, setSaved] = useState(false);
  const [testStatus, setTestStatus] = useState<TestStatus>('idle');
  const [testMessage, setTestMessage] = useState('');

  // 骨架列表（从后端 GET /skeletons 拉取）
  const [skeletons, setSkeletons] = useState<Skeleton[]>([]);
  const [skeletonsLoading, setSkeletonsLoading] = useState(true);
  const [skeletonsError, setSkeletonsError] = useState<string | null>(null);
  const [serverDefaultSkill, setServerDefaultSkill] = useState<string | null>(null);

  useEffect(() => {
    setFormData(config);
  }, [config]);

  // 进入页面就拉一次智能体列表（用当前配置的 apiBaseUrl）
  useEffect(() => {
    const ac = new AbortController();
    setSkeletonsLoading(true);
    setSkeletonsError(null);
    fetchSkeletons(config.apiBaseUrl, ac.signal)
      .then((data) => {
        setSkeletons(data.skeletons);
        setServerDefaultSkill(data.default);
        setFormData((prev) => {
          if (data.skeletons.some((s) => s.id === prev.defaultSkill)) return prev;
          return { ...prev, defaultSkill: data.default };
        });
      })
      .catch((err) => {
        if ((err as Error).name === 'AbortError') return;
        setSkeletonsError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => setSkeletonsLoading(false));
    return () => ac.abort();
  }, [config.apiBaseUrl]);

  const handleChange = <K extends keyof AppConfig>(field: K, value: AppConfig[K]) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    setSaved(false);
  };

  const handleSave = (e: FormEvent) => {
    e.preventDefault();
    setConfig(formData);
    setSkill(formData.defaultSkill);
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  };

  const handleReset = () => {
    resetConfig();
    setSaved(false);
  };

  const handleTestConnection = async () => {
    setTestStatus('testing');
    setTestMessage('');

    try {
      const data = await fetchHealth(formData.apiBaseUrl);
      if (data.status === 'ok') {
        setTestStatus('success');
        const agentName = data.agent?.name ? `（Agent: ${data.agent.name}）` : '';
        setTestMessage(`✓ 连接成功！后端健康 ${agentName}`);
      } else {
        setTestStatus('error');
        setTestMessage(`✗ 后端返回异常状态: ${data.status}`);
      }
    } catch (err) {
      setTestStatus('error');
      setTestMessage(`✗ 连接失败: ${err instanceof Error ? err.message : String(err)}`);
    }
  };

  const goToChat = () => {
    setConfig(formData);
    setSkill(formData.defaultSkill);
    navigate('/chat');
  };

  return (
    <div className="bg-muted/30 h-full overflow-y-auto p-6 md:p-8">
      <div className="mx-auto max-w-2xl">
        {/* 头部 */}
        <div className="mb-6 flex items-center gap-3">
          <div className="bg-primary text-primary-foreground flex h-10 w-10 items-center justify-center rounded-lg">
            <SettingsIcon size={20} />
          </div>
          <div>
            <h1 className="text-xl font-semibold">系统配置</h1>
            <p className="text-muted-foreground text-sm">配置 Study AI Agent 连接参数</p>
          </div>
        </div>

        <form
          onSubmit={handleSave}
          className="bg-card border-border space-y-5 rounded-xl border p-6 shadow-sm"
        >
          {/* API 基础地址 */}
          <div className="space-y-1.5">
            <label className="text-sm font-medium">API 基础地址</label>
            <input
              type="text"
              value={formData.apiBaseUrl}
              onChange={(e) => handleChange('apiBaseUrl', e.target.value)}
              className="border-input bg-background ring-offset-background placeholder:text-muted-foreground focus-visible:ring-ring w-full rounded-md border px-3 py-2 text-sm transition-colors outline-none focus-visible:ring-2"
              placeholder="http://localhost:8000"
            />
            <p className="text-muted-foreground text-xs">
              后端 API 服务地址（同时作为健康检查与 AG-UI 端点的 baseURL）
            </p>
          </div>

          {/* 模拟模式 */}
          <div className="bg-muted/30 flex items-center justify-between rounded-lg border p-4">
            <div>
              <label className="text-sm font-medium">模拟模式</label>
              <p className="text-muted-foreground text-xs">
                使用模拟数据进行测试，不连接真实后端（仅离线 / 演示使用）
              </p>
            </div>
            <label className="relative inline-flex h-6 w-11 shrink-0 cursor-pointer items-center">
              <input
                type="checkbox"
                className="peer sr-only"
                checked={formData.mockMode}
                onChange={(e) => handleChange('mockMode', e.target.checked)}
              />
              <span
                className={cn(
                  'absolute inset-0 rounded-full transition-colors',
                  formData.mockMode
                    ? 'bg-primary'
                    : 'bg-input',
                )}
              />
              <span
                className={cn(
                  'bg-background absolute top-0.5 h-5 w-5 rounded-full shadow transition-transform',
                  formData.mockMode ? 'translate-x-5' : 'translate-x-0.5',
                )}
              />
            </label>
          </div>

          {/* 默认骨架 */}
          <div className="space-y-1.5">
            <label className="text-sm font-medium">默认骨架</label>
            <p className="text-muted-foreground text-xs">
              决定聊天请求走哪个 LangGraph 流水线（对应后端 GET /skeletons）
              {serverDefaultSkill && (
                <>
                  {' '}
                  · 后端默认：
                  <code className="bg-muted rounded px-1 py-0.5 text-[10px]">
                    {serverDefaultSkill}
                  </code>
                </>
              )}
            </p>

            {skeletonsLoading && (
              <div className="text-muted-foreground flex items-center gap-2 py-2 text-sm">
                <Loader2 className="h-4 w-4 animate-spin" />
                正在加载智能体列表...
              </div>
            )}

            {skeletonsError && (
              <div className="text-destructive flex items-start gap-2 py-2 text-sm">
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                <div>
                  <div>加载失败：{skeletonsError}</div>
                  <p className="text-muted-foreground mt-1 text-xs">
                    请先测试后端连接（"测试连接"按钮），或检查上方 API 基础地址。
                  </p>
                </div>
              </div>
            )}

            {!skeletonsLoading && !skeletonsError && skeletons.length === 0 && (
              <div className="text-muted-foreground py-2 text-sm">
                （后端未注册任何智能体）
              </div>
            )}

            {!skeletonsLoading && !skeletonsError && skeletons.length > 0 && (
              <div className="space-y-2">
                {skeletons.map((sk) => {
                  const isSelected = formData.defaultSkill === sk.id;
                  return (
                    <label
                      key={sk.id}
                      className={cn(
                        'flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition-colors',
                        isSelected
                          ? 'border-primary bg-primary/5'
                          : 'border-border hover:bg-muted/50',
                      )}
                    >
                      <input
                        type="radio"
                        name="defaultSkill"
                        value={sk.id}
                        checked={isSelected}
                        onChange={() => handleChange('defaultSkill', sk.id)}
                        className="text-primary mt-1 h-4 w-4"
                      />
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-medium">{sk.name}</span>
                          <code className="bg-muted rounded px-1.5 py-0.5 text-[10px]">
                            {sk.id}
                          </code>
                          <span className="text-muted-foreground text-xs">
                            {sk.tool_count} 工具
                          </span>
                          {sk.id === serverDefaultSkill && (
                            <span className="bg-primary/10 text-primary rounded-full px-2 py-0.5 text-[10px]">
                              默认
                            </span>
                          )}
                        </div>
                        <p className="text-muted-foreground mt-1 text-xs leading-relaxed">
                          {sk.description}
                        </p>
                        {Object.keys(sk.hitl_rules).length > 0 && (
                          <p className="text-muted-foreground mt-1 text-[11px]">
                            HITL：{Object.keys(sk.hitl_rules).length} 个工具需要人工审批
                          </p>
                        )}
                      </div>
                    </label>
                  );
                })}
              </div>
            )}
          </div>

          {/* 操作按钮 */}
          <div className="flex flex-wrap items-center gap-2 pt-2">
            <Button type="submit" className="min-w-32">
              <Save size={14} />
              {saved ? '✓ 已保存' : '保存配置'}
            </Button>
            <Button
              type="button"
              variant="secondary"
              onClick={handleTestConnection}
              disabled={testStatus === 'testing'}
            >
              {testStatus === 'testing' ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Wifi size={14} />
              )}
              {testStatus === 'testing' ? '测试中...' : '测试连接'}
            </Button>
            <Button type="button" variant="ghost" onClick={handleReset}>
              <RotateCcw size={14} />
              重置
            </Button>
            <Button type="button" variant="link" onClick={goToChat} className="ml-auto">
              去聊天 →
            </Button>
          </div>

          {testMessage && (
            <div
              className={cn(
                'flex items-start gap-2 rounded-md px-3 py-2 text-sm',
                testStatus === 'success' && 'bg-green-50 text-green-700',
                testStatus === 'error' && 'bg-red-50 text-red-700',
                testStatus === 'testing' && 'bg-blue-50 text-blue-700',
              )}
            >
              {testStatus === 'success' ? (
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
              ) : testStatus === 'error' ? (
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
              ) : (
                <Loader2 className="mt-0.5 h-4 w-4 shrink-0 animate-spin" />
              )}
              <span>{testMessage}</span>
            </div>
          )}
        </form>

        {/* 配置预览 */}
        <details className="bg-card border-border mt-4 rounded-xl border p-4 shadow-sm">
          <summary className="text-primary cursor-pointer text-sm font-medium">
            查看当前配置
          </summary>
          <pre className="bg-foreground text-background mt-3 overflow-x-auto rounded-md p-3 font-mono text-xs">
            {JSON.stringify(formData, null, 2)}
          </pre>
        </details>
      </div>
    </div>
  );
}
