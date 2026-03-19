/**
 * 考点标签组组件
 *
 * [INPUT]: 依赖 antd Tag、Tooltip，@/types，./PointTag
 * [OUTPUT]: 对外提供 PointTagGroup 组件
 * [POS]: frontend/src/components/cloze 的考点标签组组件
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 *
 * 功能：
 * - 组合展示主考点 + 辅助考点 + 排错点
 * - 折叠/展开超过 N 个的辅助考点
 * - 悬停显示详细 Tooltip
 * - 支持不同布局方向
 */
import { useState, useMemo } from 'react'
import { Tag, Space, Tooltip, Typography } from 'antd'

import type { PointType, SecondaryPoint, RejectionPoint } from '@/types'
import { CATEGORY_NAMES, PRIORITY_NAMES } from '@/types'
import { PointTag, MoreTag, type PointTagSize } from './PointTag'
import styles from './PointTag.module.css'

const { Text } = Typography

// ============================================================================
//  考点编码到中文名称的映射
// ============================================================================

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

export interface PointTagGroupProps {
  /** 主考点 */
  primaryPoint?: PointType
  /** 辅助考点列表 */
  secondaryPoints?: SecondaryPoint[]
  /** 排错点列表 */
  rejectionPoints?: RejectionPoint[]
  /** 辅助考点最大可见数量 */
  maxSecondaryVisible?: number
  /** 排错点最大可见数量 */
  maxRejectionVisible?: number
  /** 标签尺寸 */
  size?: PointTagSize
  /** 是否显示排错点 */
  showRejection?: boolean
  /** 是否显示辅助考点 */
  showSecondary?: boolean
  /** 布局方向 */
  direction?: 'horizontal' | 'vertical'
  /** 考点类型映射（用于从编码获取完整信息） */
  pointTypeMap?: Map<string, PointType>
  /** 紧凑模式（仅显示编码） */
  compact?: boolean
  /** 点击考点标签 */
  onPointClick?: (code: string) => void
  /** 自定义类名 */
  className?: string
}

// ============================================================================
//  辅助组件
// ============================================================================

/** 辅助考点标签（带解析说明，V5 支持 co-primary） */
function SecondaryPointTag({
  point,
  size,
  onClick,
}: {
  point: SecondaryPoint
  pointTypeMap?: Map<string, PointType>
  size: PointTagSize
  compact?: boolean
  onClick?: () => void
}) {
  const displayName = getPointDisplayName(point.point_code)
  const isCoPrimary = point.weight === 'co-primary'

  const tooltipContent = (
    <div>
      <div>
        <strong>{displayName}</strong>
        {isCoPrimary && <span style={{ color: '#fa8c16', marginLeft: 4 }}>（联合主考点）</span>}
      </div>
      {point.explanation && (
        <div style={{ fontSize: 11, color: '#8c8c8c', marginTop: 2 }}>
          {point.explanation}
        </div>
      )}
    </div>
  )

  // V5: co-primary 使用金色虚线边框
  const tagStyle = isCoPrimary
    ? {
        fontSize: size === 'l' ? 11 : size === 'xs' ? 9 : 10,
        background: '#fffbe6',
        borderColor: '#ffc53d',
        borderStyle: 'dashed' as const,
        color: '#d48806',
      }
    : { fontSize: size === 'l' ? 11 : size === 'xs' ? 9 : 10 }

  return (
    <Tooltip title={tooltipContent} mouseEnterDelay={0.3}>
      <Tag
        className={isCoPrimary ? '' : styles.secondaryTag}
        style={tagStyle}
        onClick={onClick}
      >
        {displayName}
        {isCoPrimary && <span style={{ marginLeft: 2 }}>⚡</span>}
      </Tag>
    </Tooltip>
  )
}

/** 排错点标签 */
function RejectionPointTag({
  point,
  size,
}: {
  point: RejectionPoint
  pointTypeMap?: Map<string, PointType>
  size: PointTagSize
}) {
  const displayName = getPointDisplayName(point.point_code)

  const tooltipContent = (
    <div>
      <div>
        <Text delete type="danger">{point.option_word}</Text>
        <Text type="secondary" style={{ marginLeft: 4 }}>
          ← {displayName}
        </Text>
      </div>
      {point.explanation && (
        <div style={{ fontSize: 11, color: '#8c8c8c', marginTop: 2 }}>
          {point.explanation}
        </div>
      )}
    </div>
  )

  return (
    <Tooltip title={tooltipContent} mouseEnterDelay={0.3}>
      <Tag
        className={styles.rejectionTag}
        style={{ fontSize: size === 'l' ? 11 : size === 'xs' ? 9 : 10 }}
      >
        <Text delete style={{ color: '#cf1322' }}>{point.option_word}</Text>
        <Text type="secondary" style={{ marginLeft: 4, fontSize: 'inherit' }}>
          ← {displayName}
        </Text>
      </Tag>
    </Tooltip>
  )
}

// ============================================================================
//  主组件
// ============================================================================

export function PointTagGroup({
  primaryPoint,
  secondaryPoints = [],
  rejectionPoints = [],
  maxSecondaryVisible = 2,
  maxRejectionVisible = 1,
  size = 'm',
  showRejection = false,
  showSecondary = true,
  direction = 'horizontal',
  pointTypeMap,
  compact = false,
  onPointClick,
  className = '',
}: PointTagGroupProps) {
  const [secondaryExpanded, setSecondaryExpanded] = useState(false)
  const [rejectionExpanded, setRejectionExpanded] = useState(false)

  // 计算需要折叠的辅助考点数量
  const hiddenSecondaryCount = useMemo(() => {
    if (secondaryExpanded || secondaryPoints.length <= maxSecondaryVisible) return 0
    return secondaryPoints.length - maxSecondaryVisible
  }, [secondaryPoints.length, maxSecondaryVisible, secondaryExpanded])

  // 计算需要折叠的排错点数量
  const hiddenRejectionCount = useMemo(() => {
    if (rejectionExpanded || rejectionPoints.length <= maxRejectionVisible) return 0
    return rejectionPoints.length - maxRejectionVisible
  }, [rejectionPoints.length, maxRejectionVisible, rejectionExpanded])

  // 可见的辅助考点
  const visibleSecondaryPoints = useMemo(() => {
    if (secondaryExpanded) return secondaryPoints
    return secondaryPoints.slice(0, maxSecondaryVisible)
  }, [secondaryPoints, maxSecondaryVisible, secondaryExpanded])

  // 可见的排错点
  const visibleRejectionPoints = useMemo(() => {
    if (rejectionExpanded) return rejectionPoints
    return rejectionPoints.slice(0, maxRejectionVisible)
  }, [rejectionPoints, maxRejectionVisible, rejectionExpanded])

  // 如果没有任何考点
  if (!primaryPoint && secondaryPoints.length === 0 && rejectionPoints.length === 0) {
    return null
  }

  const containerClass = direction === 'vertical'
    ? styles.tagGroupVertical
    : styles.tagGroup

  return (
    <div className={`${containerClass} ${className}`.trim()}>
      {/* 主考点 */}
      {primaryPoint && (
        <PointTag
          point={primaryPoint}
          size={size}
          variant="primary"
          compact={compact}
          pointTypeMap={pointTypeMap}
          onClick={onPointClick ? () => onPointClick(primaryPoint.code) : undefined}
        />
      )}

      {/* 辅助考点 */}
      {showSecondary && visibleSecondaryPoints.length > 0 && (
        <>
          {visibleSecondaryPoints.map((sp, idx) => (
            <SecondaryPointTag
              key={`secondary-${idx}`}
              point={sp}
              pointTypeMap={pointTypeMap}
              size={size}
              compact={compact}
              onClick={onPointClick ? () => onPointClick(sp.point_code) : undefined}
            />
          ))}
          {/* 折叠指示器 */}
          {hiddenSecondaryCount > 0 && (
            <MoreTag
              count={hiddenSecondaryCount}
              onClick={() => setSecondaryExpanded(true)}
            />
          )}
        </>
      )}

      {/* 排错点（仅在显示时） */}
      {showRejection && visibleRejectionPoints.length > 0 && (
        <>
          {visibleRejectionPoints.map((rp, idx) => (
            <RejectionPointTag
              key={`rejection-${idx}`}
              point={rp}
              pointTypeMap={pointTypeMap}
              size={size}
            />
          ))}
          {/* 折叠指示器 */}
          {hiddenRejectionCount > 0 && (
            <MoreTag
              count={hiddenRejectionCount}
              onClick={() => setRejectionExpanded(true)}
            />
          )}
        </>
      )}
    </div>
  )
}

// ============================================================================
//  详细展示组件（用于 Popover 等场景）
// ============================================================================

export interface PointDetailSectionProps {
  primaryPoint?: PointType
  secondaryPoints?: SecondaryPoint[]
  rejectionPoints?: RejectionPoint[]
  pointTypeMap?: Map<string, PointType>
}

/** 考点详情区块（用于 Popover 内容） */
export function PointDetailSection({
  primaryPoint,
  secondaryPoints = [],
  rejectionPoints = [],
}: PointDetailSectionProps) {
  return (
    <div>
      {/* 主考点详情 */}
      {primaryPoint && (
        <div className={styles.primaryPointSection}>
          <div className={styles.primaryPointHeader}>
            <Text strong style={{ fontSize: 12 }}>
              主考点: {getPointDisplayName(primaryPoint.code)}
            </Text>
          </div>
          <div className={styles.primaryPointMeta} style={{ marginTop: 4 }}>
            <Space size={8}>
              <span>{CATEGORY_NAMES[primaryPoint.category] || primaryPoint.category}</span>
              <span>{PRIORITY_NAMES[primaryPoint.priority] || `P${primaryPoint.priority}`}</span>
            </Space>
          </div>
          {primaryPoint.description && (
            <div style={{ marginTop: 4 }}>
              <Text type="secondary" style={{ fontSize: 10 }}>
                {primaryPoint.description}
              </Text>
            </div>
          )}
        </div>
      )}

      {/* 辅助考点详情 */}
      {secondaryPoints.length > 0 && (
        <div className={styles.secondaryPointSection}>
          <Text type="secondary" className={styles.secondaryPointLabel}>
            辅助考点：
          </Text>
          <div className={styles.tagGroup}>
            {secondaryPoints.map((sp, idx) => {
              return (
                <Tooltip
                  key={idx}
                  title={sp.explanation}
                  mouseEnterDelay={0.3}
                >
                  <Tag style={{ fontSize: 11, marginBottom: 2 }}>
                    {getPointDisplayName(sp.point_code)}
                  </Tag>
                </Tooltip>
              )
            })}
          </div>
        </div>
      )}

      {/* 排错点详情 */}
      {rejectionPoints.length > 0 && (
        <div className={styles.rejectionPointSection}>
          <Text type="secondary" className={styles.rejectionPointLabel}>
            排错依据：
          </Text>
          {rejectionPoints.map((rp, idx) => {
            return (
              <div key={idx} className={styles.rejectionItem}>
                <Text delete type="danger" style={{ marginRight: 6 }}>{rp.option_word}</Text>
                <Text type="secondary">
                  ← {getPointDisplayName(rp.point_code)}
                  {rp.explanation && `: ${rp.explanation}`}
                </Text>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
