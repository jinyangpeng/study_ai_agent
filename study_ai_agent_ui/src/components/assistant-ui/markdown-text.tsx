/**
 * Markdown 渲染组件
 *
 * - 后端返回的 ``text`` 字段被 marked + highlight.js 渲染成 HTML
 * - 代码块带有语言标签 + 一键复制按钮
 * - 流式渲染时（status.type === 'running'）显示打字光标
 * - 通过 ``useEffect`` + DOM ref 注入复制按钮的事件，避免 dangerouslySetInnerHTML 失控
 */
import { memo, useEffect, useRef } from 'react';
import type { FC } from 'react';
import type { TextMessagePartComponent } from '@assistant-ui/react';

import { renderMarkdown } from '@/lib/markdown';
import { cn } from '@/lib/utils';

const MarkdownTextImpl: TextMessagePartComponent = ({ text, status }) => {
  const ref = useRef<HTMLDivElement>(null);
  const isRunning = status?.type === 'running';

  // 给代码块注入复制按钮（每次 text 变化重新绑定）
  useEffect(() => {
    const root = ref.current;
    if (!root) return;

    const codeBlocks = root.querySelectorAll<HTMLPreElement>('pre.md-code-block');
    codeBlocks.forEach((pre) => {
      // 防止重复注入
      if (pre.querySelector('button.md-copy-btn')) return;

      const btn = document.createElement('button');
      btn.className = 'md-copy-btn';
      btn.type = 'button';
      btn.title = '复制代码';
      btn.setAttribute('aria-label', '复制代码');
      btn.innerHTML =
        '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>';

      btn.addEventListener('click', () => {
        const code = pre.querySelector('code');
        const text = code?.textContent ?? '';
        void navigator.clipboard.writeText(text).then(() => {
          btn.classList.add('md-copy-btn--success');
          btn.innerHTML =
            '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>';
          window.setTimeout(() => {
            btn.classList.remove('md-copy-btn--success');
            btn.innerHTML =
              '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>';
          }, 1800);
        });
      });

      pre.appendChild(btn);
    });
  }, [text]);

  return (
    <div
      ref={ref}
      className={cn('aui-md text-sm leading-relaxed', isRunning && 'is-streaming')}
    >
      <div
        className="aui-md-body"
        dangerouslySetInnerHTML={{ __html: renderMarkdown(text) }}
      />
      {isRunning && (
        <span className="ml-0.5 inline-block h-4 w-1 -mb-0.5 animate-pulse bg-current opacity-60" />
      )}
    </div>
  );
};

export const MarkdownText = memo(MarkdownTextImpl);

// 兼容旧 default 引用（避免引入方遗留 default import 时报错）
export default MarkdownText as unknown as FC;
