import { Route, Routes } from 'react-router-dom';
import { Layout } from '@/components';
import { printEnvConfig } from '@/config';
import { Chat, Config } from '@/pages';

// 开发环境打印环境配置
printEnvConfig();

export default function App() {
  // Layout 提到 Routes 外层，Provider（Session/Skill/Config）单例化，
  // 避免在 /chat ↔ /config 之间切换时重复触发"首次进入自动建会话"，
  // 以及 Skill/Config 状态被重置（参见 dogfood ISSUE-001 / ISSUE-004）。
  return (
    <Layout>
      <Routes>
        <Route path="/config" element={<Config />} />
        <Route path="/chat" element={<Chat />} />
        <Route path="*" element={<Chat />} />
      </Routes>
    </Layout>
  );
}
