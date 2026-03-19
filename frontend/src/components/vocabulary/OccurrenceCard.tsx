/**
 * 例句卡片组件（紧凑版）
 *
 * [INPUT]: 依赖 VocabularyOccurrence 类型
 * [OUTPUT]: 对外提供 OccurrenceCard 组件
 * [POS]: frontend/src/components/vocabulary 的例句卡片
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */
import { Typography } from 'antd'

import type { VocabularyOccurrence } from '@/types'

const { Text, Paragraph } = Typography

interface OccurrenceCardProps {
  occurrence: VocabularyOccurrence
  onClick: () => void
}

export function OccurrenceCard({
  occurrence,
  onClick,
}: OccurrenceCardProps) {
  // 格式化出处信息：年份 + 区县 + 学校 + 年级 + 考试类型
  // 区县和学校都显示，没有的就空着
  const sourceParts: string[] = []
  if (occurrence.year) sourceParts.push(String(occurrence.year))
  if (occurrence.region) sourceParts.push(occurrence.region)
  if (occurrence.school) sourceParts.push(occurrence.school)
  if (occurrence.grade) sourceParts.push(occurrence.grade)
  if (occurrence.exam_type) sourceParts.push(occurrence.exam_type)

  return (
    <div
      onClick={onClick}
      style={{
        padding: '6px 10px',
        marginBottom: 4,
        cursor: 'pointer',
        transition: 'all 0.2s ease',
        borderLeft: '2px solid #1890ff',
        background: '#fafafa',
        borderRadius: '0 4px 4px 0',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = '#f0f5ff'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = '#fafafa'
      }}
    >
      {/* 出处信息 - 单行紧凑 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
        <Text style={{ fontSize: 11, color: '#666' }}>
          {sourceParts.join(' ')}
        </Text>
      </div>

      {/* 例句内容 */}
      <Paragraph
        italic
        style={{
          margin: 0,
          fontSize: 12,
          lineHeight: 1.4,
          color: '#333',
        }}
      >
        "{occurrence.sentence}"
      </Paragraph>
    </div>
  )
}
