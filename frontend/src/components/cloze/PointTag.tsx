/**
 * 考点标签组件
 *
 * [INPUT]: 依赖 antd Tag、Tooltip，@/types
 * [OUTPUT]: 对外提供 PointTag 组件
 * [POS]: frontend/src/components/cloze 的考点标签组件
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 *
 * 功能：
 * - 单个考点标签展示
 * - 支持不同尺寸 (xs/s/m/l)
 * - 支持不同变体 (primary/secondary/rejection)
 * - 显示优先级标识
 * - 悬停显示 Tooltip
 */
import { Tag, Tooltip } from 'antd'
import type { ReactNode, CSSProperties } from 'react'

import type { PointType } from '@/types'
import { CATEGORY_COLORS, CATEGORY_NAMES, PRIORITY_NAMES } from '@/types'
import styles from './PointTag.module.css'

// 考点编码到中文名称的映射
const POINT_CODE_TO_NAME: Record<string, string> = {
  // A类-语篇理解
  A1: "上下文语义",
  A2: "复现照应",
  A3: "代词指代",
  A4: "情节顺序",
  A5: "情感态度",
  // B类-逻辑关系
  B1: "并列一致",
  B2: "转折对比",
  B3: "因果关系",
  B4: "其他逻辑",
  // C类-句法语法
  C1: "词性成分",
  C2: "固定搭配",
  C3: "语法形式",
  // D类-词汇选项
  D1: "词义辨析",
  D2: "熟词僻义",
  // E类-常识主题
  E1: "生活常识",
  E2: "主题共情",
}

function getPointDisplayName(code: string): string {
  // 处理 "D2_熟词僻义" 格式，提取编码
  const actualCode = code.split('_')[0]  // 取下划线前的部分
  return POINT_CODE_TO_NAME[actualCode] || POINT_CODE_TO_NAME[code] || code
}

// ============================================================================
//  类型定义
// ============================================================================

export type PointTagSize = 'xs' | 's' | 'm' | 'l'
export type PointTagVariant = 'primary' | 'secondary' | 'rejection'

export interface PointTagProps {
  /** 考点信息（完整或简化） */
  point?: PointType | { code: string; name?: string; category?: string; priority?: number }
  /** 标签尺寸 */
  size?: PointTagSize
  /** 标签变体 */
  variant?: PointTagVariant
  /** 是否显示优先级标识 */
  showPriority?: boolean
  /** 是否显示大类标识 */
  showCategory?: boolean
  /** 紧凑模式（仅显示编码） */
  compact?: boolean
  /** 自定义类名 */
  className?: string
  /** 自定义样式 */
  style?: CSSProperties
  /** 子元素（替代默认内容） */
  children?: ReactNode
  /** 点击事件 */
  onClick?: () => void
  /** 考点类型映射（用于从编码获取完整信息） */
  pointTypeMap?: Map<string, PointType>
}

// ============================================================================
//  常量定义
// ============================================================================

// 尺寸样式映射
const SIZE_STYLES: Record<PointTagSize, CSSProperties> = {
  xs: { fontSize: 9, padding: '1px 4px', lineHeight: '14px' },
  s: { fontSize: 10, padding: '2px 6px', lineHeight: '16px' },
  m: { fontSize: 11, padding: '2px 8px', lineHeight: '18px' },
  l: { fontSize: 12, padding: '4px 10px', lineHeight: '20px' },
}

// 优先级对应的 CSS 类名
const PRIORITY_CLASS: Record<number, string> = {
  1: styles.priorityHigh,
  2: styles.priorityMedium,
  3: styles.priorityLow,
}

// ============================================================================
//  主组件
// ============================================================================

export function PointTag({
  point,
  size = 'm',
  variant = 'primary',
  showPriority: _showPriority = false,  // TODO: 未来支持显示优先级标识
  showCategory: _showCategory = false,  // TODO: 未来支持显示大类标识
  compact: _compact = false,
  className = '',
  style,
  children,
  onClick,
}: PointTagProps) {
  // 如果没有考点信息，返回空
  if (!point && !children) {
    return null
  }

  const code = point?.code || ''
  const category = point?.category || ''
  const priority = point?.priority || 3

  // 确定标签颜色
  const getTagColor = (): string => {
    if (variant === 'secondary') return 'default'
    if (variant === 'rejection') return 'error'
    if (category && CATEGORY_COLORS[category]) {
      return CATEGORY_COLORS[category]
    }
    // 从编码推断大类
    const categoryCode = code?.charAt(0)
    if (categoryCode && CATEGORY_COLORS[categoryCode]) {
      return CATEGORY_COLORS[categoryCode]
    }
    return 'default'
  }

  // 构建显示内容
  const getDisplayContent = (): ReactNode => {
    if (children) return children
    // 显示 "编码 名称" 格式，如 "D1 词义辨析"
    const displayName = getPointDisplayName(code)
    const actualCode = code?.split('_')[0] || code
    // 如果编码是标准的 A1-E2 格式，显示 "编码 名称"
    if (/^[A-E][1-5]$/.test(actualCode)) {
      return `${actualCode} ${displayName}`
    }
    return displayName
  }

  // 构建 Tooltip 内容
  const getTooltipContent = (): ReactNode => {
    if (!point) return getPointDisplayName(code)

    const parts: string[] = []
    parts.push(getPointDisplayName(code))
    if (category && CATEGORY_NAMES[category]) {
      parts.push(`大类：${CATEGORY_NAMES[category]}`)
    }
    if (priority && PRIORITY_NAMES[priority]) {
      parts.push(`优先级：${PRIORITY_NAMES[priority]}`)
    }

    return parts.join(' · ')
  }

  // 构建优先级样式类
  const getPriorityClass = (): string => {
    if (variant !== 'primary') return ''
    return PRIORITY_CLASS[priority] || PRIORITY_CLASS[3]
  }

  // 构建变体样式类
  const getVariantClass = (): string => {
    if (variant === 'secondary') return styles.secondaryTag
    if (variant === 'rejection') return styles.rejectionTag
    return ''
  }

  // 合并样式
  const mergedStyle: CSSProperties = {
    ...SIZE_STYLES[size],
    ...style,
    cursor: onClick ? 'pointer' : undefined,
    borderRadius: size === 'xs' ? 4 : size === 'l' ? 8 : 6,
  }

  const tagElement = (
    <Tag
      color={getTagColor()}
      className={`${getPriorityClass()} ${getVariantClass()} ${className}`.trim()}
      style={mergedStyle}
      onClick={onClick}
    >
      {getDisplayContent()}
    </Tag>
  )

  // 如果有完整信息，包裹 Tooltip
  if (point || code) {
    return (
      <Tooltip title={getTooltipContent()} mouseEnterDelay={0.3}>
        {tagElement}
      </Tooltip>
    )
  }

  return tagElement
}

// ============================================================================
//  辅助组件
// ============================================================================

/** 空格标签（用于原文中的空格位置） */
export function BlankTag({
  blankNumber,
  point,
  selected = false,
  onClick,
}: {
  blankNumber: number
  point?: PointType
  selected?: boolean
  onClick?: () => void
}) {
  const category = point?.category || ''
  const priority = point?.priority || 3
  const color = category ? CATEGORY_COLORS[category] : 'default'
  const priorityClass = PRIORITY_CLASS[priority] || ''

  return (
    <Tag
      color={color}
      className={`${priorityClass} ${styles.blankTag} ${selected ? styles.blankTagSelected : ''}`.trim()}
      style={{
        cursor: 'pointer',
        fontSize: 14,
        padding: '2px 10px',
        margin: '0 2px',
        transition: 'all 0.3s ease',
      }}
      onClick={onClick}
    >
      {blankNumber}
    </Tag>
  )
}

/** 折叠指示器标签 */
export function MoreTag({
  count,
  onClick,
}: {
  count: number
  onClick?: () => void
}) {
  return (
    <Tag
      className={styles.moreTag}
      onClick={onClick}
      style={{ cursor: onClick ? 'pointer' : 'default' }}
    >
      +{count}
    </Tag>
  )
}
