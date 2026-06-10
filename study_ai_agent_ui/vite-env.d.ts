/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** 应用端口 */
  readonly VITE_PORT: string;
  /** 应用主机 */
  readonly VITE_HOST: string;
  /** API 基础地址 */
  readonly VITE_API_BASE_URL: string;
  /** CopilotKit 运行时 URL */
  readonly VITE_COPILOT_RUNTIME_URL: string;
  /** OpenAI API Key (仅本地开发使用) */
  readonly VITE_OPENAI_API_KEY: string;
  /** OpenAI 模型名称 */
  readonly VITE_OPENAI_MODEL: string;
  /** 应用标题 */
  readonly VITE_APP_TITLE: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
