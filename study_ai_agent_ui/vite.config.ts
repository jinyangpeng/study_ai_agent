import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');

  const apiTarget = env.VITE_API_BASE_URL || 'http://localhost:8000';

  return {
    plugins: [react()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      port: Number(env.VITE_PORT) || 3000,
      host: env.VITE_HOST || 'localhost',
      open: true,
      proxy: {
        // 后端 API
        '/api': {
          target: apiTarget,
          changeOrigin: true,
        },
        // 健康检查
        '/health': {
          target: apiTarget,
          changeOrigin: true,
        },
      },
    },
  };
});
