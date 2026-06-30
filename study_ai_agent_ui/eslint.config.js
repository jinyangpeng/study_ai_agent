/**
 * ESLint v9 flat config
 *
 * 规则策略：
 *   - TypeScript 严格模式（继承 tsconfig.json 的 strict）
 *   - React 17+ JSX Runtime (jsx: react-jsx)
 *   - React Hooks 规则
 *   - 适度限制未使用变量/参数（保留以 `_` 开头的逃逸）
 *   - 控制台日志需要显式注释
 */
import js from '@eslint/js';
import globals from 'globals';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import tseslint from '@typescript-eslint/eslint-plugin';
import tsParser from '@typescript-eslint/parser';

export default [
  {
    ignores: ['dist/**', 'node_modules/**', '*.config.js', '*.config.ts'],
  },
  js.configs.recommended,
  {
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'module',
      parser: tsParser,
      parserOptions: {
        ecmaFeatures: { jsx: true },
      },
      globals: {
        ...globals.browser,
        ...globals.es2022,
      },
    },
    plugins: {
      '@typescript-eslint': tseslint,
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    rules: {
      ...tseslint.configs.recommended.rules,
      // React Hooks 只启用稳定版规则（v7+ 的 react-hooks/refs / set-state-in-effect
      // 仍处于 experimental 阶段，对于使用 ref 转发状态的场景会误报）
      'react-hooks/rules-of-hooks': 'error',
      'react-hooks/exhaustive-deps': 'warn',
      // Vite HMR
      'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
      // 通用
      'no-console': ['warn', { allow: ['warn', 'error'] }],
      'no-debugger': 'warn',
      'prefer-const': 'warn',
      eqeqeq: ['warn', 'always', { null: 'ignore' }],
    },
  },
  {
    files: ['src/**/*.{ts,tsx}'],
    rules: {
      '@typescript-eslint/consistent-type-imports': [
        'warn',
        { prefer: 'type-imports', fixStyle: 'inline-type-imports' },
      ],
    },
  },
  // Context 文件同时导出 Provider 组件和 hook 是惯用做法，
  // 关掉 fast-refresh 提示以减少噪音。
  {
    files: [
      'src/context/ConfigContext.tsx',
      'src/context/SkillContext.tsx',
      'src/context/AguiStateContext.tsx',
    ],
    rules: {
      'react-refresh/only-export-components': 'off',
    },
  },
];
