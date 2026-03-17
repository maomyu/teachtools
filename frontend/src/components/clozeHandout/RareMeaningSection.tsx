/**
 * 熟词僻义展示组件
 *
 * [INPUT]: 依赖 antd, types
 * [OUTPUT]: 对外提供 RareMeaningSection 组件
 * [POS]: frontend/src/components/clozeHandout 的熟词僻义展示
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */
import { Typography, Tag, Space } from 'antd'
import type { RareMeaningPoint } from '@/types'

const { Text } = Typography

// ============================================================================
//  Props 定义
// ============================================================================

interface RareMeaningSectionProps {
  points: RareMeaningPoint[]
  edition: 'teacher' | 'student'
  startIndex?: number  // 起始序号（用于分页）
}

// ============================================================================
//  主组件：熟词僻义展示
// ============================================================================

export function RareMeaningSection({ points, edition, startIndex = 0 }: RareMeaningSectionProps) {
  if (!points || points.length === 0) {
    return <Text type="secondary">暂无熟词僻义数据</Text>
  }

  return (
    <div className="rare-meaning-list">
      {points.map((point, idx) => (
        <RareMeaningItem
          key={`${point.word}-${idx}`}
          point={point}
          edition={edition}
          index={startIndex + idx + 1}
        />
      ))}
    </div>
  )
}

// ============================================================================
//  子组件：单个熟词僻义项
// ============================================================================

interface RareMeaningItemProps {
  point: RareMeaningPoint
  edition: 'teacher' | 'student'
  index: number
}

function RareMeaningItem({ point, edition, index }: RareMeaningItemProps) {
  const { word, frequency, textbook_meaning, textbook_source, context_meaning, similar_words, occurrences } = point

  return (
    <div className="rare-meaning-item" style={{ padding: '16px 0', borderBottom: '1px solid #f0f0f0' }}>
      {/* 标题行 */}
      <div className="rare-meaning-header" style={{ marginBottom: 8 }}>
        <Space>
          <Text strong style={{ fontSize: 14 }}>{index}. {word}</Text>
          <Tag color="purple">{frequency}次</Tag>
        </Space>
      </div>

      {/* 课本出处 */}
      {textbook_source && (
        <Text type="secondary" style={{ fontSize: 11, display: 'block', marginBottom: 12 }}>
          课本出处：{textbook_source}
        </Text>
      )}

      {/* 释义对比表格 */}
      <table className="meaning-compare-table" style={{
        width: '100%',
        borderCollapse: 'collapse',
        marginBottom: 12,
        fontSize: '11pt'
      }}>
        <thead>
          <tr>
            <th style={{
              width: '45%',
              border: '1px solid #d9d9d9',
              padding: '8px 12px',
              background: '#f5f5f5',
              textAlign: 'center'
            }}>
              课本释义（熟义）
            </th>
            <th style={{
              width: '10%',
              border: '1px solid #d9d9d9',
              padding: '8px 12px',
              background: '#f5f5f5',
              textAlign: 'center'
            }}>
              →
            </th>
            <th style={{
              width: '45%',
              border: '1px solid #d9d9d9',
              padding: '8px 12px',
              background: '#f5f5f5',
              textAlign: 'center'
            }}>
              语境释义（生义）
            </th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td style={{
              border: '1px solid #d9d9d9',
              padding: '10px 12px',
              textAlign: 'center'
            }}>
              {textbook_meaning || '-'}
            </td>
            <td style={{
              border: '1px solid #d9d9d9',
              padding: '10px 12px',
              textAlign: 'center',
              fontWeight: 'bold',
              color: '#722ed1'
            }}>
              →
            </td>
            <td style={{
              border: '1px solid #d9d9d9',
              padding: '10px 12px',
              textAlign: 'center',
              color: '#722ed1',
              fontWeight: 'bold'
            }}>
              {context_meaning || '-'}
            </td>
          </tr>
        </tbody>
      </table>

      {/* 教师版：其他熟词僻义示例 */}
      {edition === 'teacher' && similar_words && similar_words.length > 0 && (
        <div className="similar-words" style={{ marginBottom: 8 }}>
          <Text type="secondary" style={{ display: 'block', marginBottom: 8 }}>
            其他熟词僻义示例：
          </Text>
          <div className="similar-words-list" style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
            {similar_words.map((item, idx) => (
              <Tag key={idx} color="purple" style={{ margin: 0 }}>
                {item.word}: {item.textbook} → {item.rare}
              </Tag>
            ))}
          </div>
        </div>
      )}

    </div>
  )
}
