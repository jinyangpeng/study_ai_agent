/**
 * Markdown 渲染器（marked + highlight.js）
 *
 * 设计目标：
 *   - 安全：默认转义 HTML
 *   - 高亮：highlight.js，附带语言标签
 *   - 兼容 React 18
 *   - 包大小可控：仅注册常用语言
 */
import { marked } from 'marked';
import hljs from 'highlight.js/lib/core';

// 按需注册常用语言
import bash from 'highlight.js/lib/languages/bash';
import c from 'highlight.js/lib/languages/c';
import cpp from 'highlight.js/lib/languages/cpp';
import csharp from 'highlight.js/lib/languages/csharp';
import css from 'highlight.js/lib/languages/css';
import diff from 'highlight.js/lib/languages/diff';
import go from 'highlight.js/lib/languages/go';
import java from 'highlight.js/lib/languages/java';
import javascript from 'highlight.js/lib/languages/javascript';
import json from 'highlight.js/lib/languages/json';
import kotlin from 'highlight.js/lib/languages/kotlin';
import markdownLang from 'highlight.js/lib/languages/markdown';
import objectivec from 'highlight.js/lib/languages/objectivec';
import php from 'highlight.js/lib/languages/php';
import plaintext from 'highlight.js/lib/languages/plaintext';
import python from 'highlight.js/lib/languages/python';
import r from 'highlight.js/lib/languages/r';
import ruby from 'highlight.js/lib/languages/ruby';
import rust from 'highlight.js/lib/languages/rust';
import scala from 'highlight.js/lib/languages/scala';
import scss from 'highlight.js/lib/languages/scss';
import shell from 'highlight.js/lib/languages/shell';
import sql from 'highlight.js/lib/languages/sql';
import swift from 'highlight.js/lib/languages/swift';
import typescript from 'highlight.js/lib/languages/typescript';
import xml from 'highlight.js/lib/languages/xml';
import yaml from 'highlight.js/lib/languages/yaml';

const LANGS: Array<[string, unknown]> = [
  ['bash', bash],
  ['c', c],
  ['cpp', cpp],
  ['csharp', csharp],
  ['css', css],
  ['diff', diff],
  ['go', go],
  ['java', java],
  ['javascript', javascript],
  ['json', json],
  ['kotlin', kotlin],
  ['markdown', markdownLang],
  ['objectivec', objectivec],
  ['php', php],
  ['plaintext', plaintext],
  ['python', python],
  ['r', r],
  ['ruby', ruby],
  ['rust', rust],
  ['scala', scala],
  ['scss', scss],
  ['shell', shell],
  ['sql', sql],
  ['swift', swift],
  ['typescript', typescript],
  ['xml', xml],
  ['yaml', yaml],
];
LANGS.forEach(([name, lang]) => hljs.registerLanguage(name, lang as never));

const renderer = new marked.Renderer();

renderer.code = ({ text, lang }) => {
  const language = (lang ?? '').trim().split(/\s+/)[0] || 'plaintext';
  const isKnown = !!hljs.getLanguage(language);
  const target = isKnown ? language : 'plaintext';
  let highlighted: string;
  try {
    highlighted = hljs.highlight(text, { language: target, ignoreIllegals: true }).value;
  } catch {
    highlighted = escapeHtml(text);
  }
  return `<pre class="md-code-block" data-lang="${escapeAttr(language)}"><code class="hljs language-${escapeAttr(target)}">${highlighted}</code></pre>`;
};

renderer.link = ({ href, title, text }) => {
  const safeHref = href ?? '#';
  const t = title ? ` title="${escapeAttr(title)}"` : '';
  return `<a class="md-link" href="${escapeAttr(safeHref)}"${t} target="_blank" rel="noopener noreferrer">${text}</a>`;
};

marked.setOptions({
  gfm: true,
  breaks: true,
  renderer,
});

/** 渲染 Markdown → HTML 字符串 */
export function renderMarkdown(md: string): string {
  if (!md) return '';
  const html = marked.parse(md, { async: false });
  return typeof html === 'string' ? html : '';
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function escapeAttr(s: string): string {
  return escapeHtml(s);
}
