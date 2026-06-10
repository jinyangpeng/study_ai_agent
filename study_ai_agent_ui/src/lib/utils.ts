/**
 * 合并 Tailwind className 的标准工具（shadcn 风格）
 *
 * - clsx: 处理条件 className（boolean / array / object）
 * - tailwind-merge: 合并时去除冲突的 Tailwind 类（如 `px-2` vs `px-4`）
 */
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
