import { Route, Routes } from 'react-router-dom';
import { Layout } from '@/components';
import { printEnvConfig } from '@/config';
import { Chat, Config } from '@/pages';

// 开发环境打印环境配置
printEnvConfig();

export default function App() {
  return (
    <Routes>
      <Route path="/config" element={<Layout><Config /></Layout>} />
      <Route path="/chat" element={<Layout><Chat /></Layout>} />
      <Route path="*" element={<Layout><Chat /></Layout>} />
    </Routes>
  );
}
