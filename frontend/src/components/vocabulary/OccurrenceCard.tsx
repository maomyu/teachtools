/**
 * 例句卡片组件（简化版）
 *
 * [INPUT]: 依赖 VocabularyOccurrence 类型
 * [OUTPUT]: 对外提供 OccurrenceCard 组件
 * [POS]: frontend/src/components/vocabulary 的例句卡片
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */
import { Card, Tag, Typography, Space } from 'antd'
import { FileTextOutlined } from '@ant-design/icons'

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
  return (
    <Card
      size="small"
      hoverable
      onClick={onClick}
      style={{
        marginBottom: 8,
        cursor: 'pointer',
        transition: 'all 0.2s ease',
        borderLeft: '3px solid #1890ff',
      }}
      styles={{ body: { padding: '12px 16px' } }}
    >
      <Space direction="vertical" style={{ width: '100%' }} size="small">
        {/* 出处标签 */}
        <Space>
          <Tag color="green">{occurrence.source || '未知出处'}</Tag>
          {occurrence.char_position !== undefined && (
            <Text type="secondary" style={{ fontSize: 12 }}>
              位置: {occurrence.char_position}
            </Text>
          )}
        </Space>

        {/* 例句内容 */}
        <Paragraph
          italic
          style={{
            margin: '8px 0 0 0',
            fontSize: 14,
            lineHeight: 1.6,
            color: '#333',
          }}
        >
          "{occurrence.sentence}"
        </Paragraph>

        {/* 点击提示 */}
        <Space style={{ marginTop: 4 }}>
          <FileTextOutlined style={{ fontSize: 12, color: '#1890ff' }} />
          <Text type="secondary" style={{ fontSize: 12, color: '#1890ff' }}>
            点击查看原文
          </Text>
        </Space>
      </Space>
    </Card>
  )
}
