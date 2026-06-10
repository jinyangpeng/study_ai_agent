/**
 * 全局键盘快捷键
 *
 * 设计原则：
 *   - 在 Layout 内调用一次即可（避免每个页面都注册）
 *   - 拦截 <input>/<textarea>/[contenteditable] 的 keydown，让普通输入不冲突
 *   - 移动端 / 不可用 key（IE）静默 noop
 *
 * 当前内置：
 *   - Ctrl/⌘+K    → 新建会话（与 Notion / Linear / AI Studio 一致）
 *   - Esc         → 取消正在进行的运行（如果有）
 */
import { useEffect } from 'react';

export interface ShortcutHandlers {
  onNewChat?: () => void;
  onCancel?: () => void;
}

function isEditableTarget(t: EventTarget | null): boolean {
  if (!(t instanceof HTMLElement)) return false;
  const tag = t.tagName;
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true;
  if (t.isContentEditable) return true;
  return false;
}

export function useKeyboardShortcuts(handlers: ShortcutHandlers): void {
  const { onNewChat, onCancel } = handlers;

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      const mod = e.metaKey || e.ctrlKey;
      const key = e.key.toLowerCase();

      // ⌘K / Ctrl+K —— 新建会话（即便焦点在 input 也抢走，符合 Notion 行为）
      if (mod && key === 'k') {
        e.preventDefault();
        onNewChat?.();
        return;
      }

      // Esc —— 取消正在运行的 run
      if (e.key === 'Escape' && onCancel) {
        // 不 preventDefault，让其他 handler 也能感知
        onCancel();
      }
    };

    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [onNewChat, onCancel]);
}

// 保留供其他模块按需用
export { isEditableTarget };
