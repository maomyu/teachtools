/**
 * 作文讲义页面
 *
 * [INPUT]: 依赖 WritingHandoutView 组件
 * [OUTPUT]: 对外提供 WritingHandoutPage 组件
 * [POS]: frontend/src/pages 的作文讲义页面
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */
import { WritingHandoutView } from '@/components/writingHandout/WritingHandoutView'

export function WritingHandoutPage() {
  return <WritingHandoutView />
}
