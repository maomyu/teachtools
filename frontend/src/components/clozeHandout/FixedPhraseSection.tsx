/**
 * 固定搭配展示组件
 *
 * [INPUT]: 依赖 antd, types
 * [OUTPUT]: 对外提供 FixedPhraseSection 组件
 * [POS]: frontend/src/components/clozeHandout 的固定搭配展示
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */
import { Typography, Tag, Space } from 'antd'
import type { FixedPhrasePoint } from '@/types'

const { Text } = Typography

// ============================================================================
//  Props 定义
// ============================================================================

interface FixedPhraseSectionProps {
  points: FixedPhrasePoint[]
  edition: 'teacher' | 'student'
  startIndex?: number  // 起始序号（用于分页）
}

// ============================================================================
//  主组件：固定搭配展示
// ============================================================================

export function FixedPhraseSection({ points, edition, startIndex = 0 }: FixedPhraseSectionProps) {
  if (!points || points.length === 0) {
    return <Text type="secondary">暂无固定搭配数据</Text>
  }

  return (
    <div className="fixed-phrase-list">
      {points.map((point, idx) => (
        <FixedPhraseItem
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
//  子组件：单个固定搭配项
// ============================================================================

interface FixedPhraseItemProps {
  point: FixedPhrasePoint
  edition: 'teacher' | 'student'
  index: number
}

function FixedPhraseItem({ point, edition, index }: FixedPhraseItemProps) {
  const { word, frequency, phrase, similar_phrases, occurrences } = point

  return (
    <div className="phrase-item" style={{ padding: '12px 0', borderBottom: '1px dashed #e8e8e8' }}>
      {/* 标题行 */}
      <div className="phrase-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <Space>
          <Text strong style={{ fontSize: 14 }}>{index}. {word}</Text>
          <Tag color="green">{frequency}次</Tag>
        </Space>
      </div>

      {/* 完整短语 */}
      <div className="phrase-content" style={{ marginBottom: 8 }}>
        <Space>
          <Text type="secondary">短语：</Text>
          <Text code style={{ fontSize: 13, fontWeight: 'bold' }}>{phrase || word}</Text>
        </Space>
      </div>

      {/* 教师版：相似短语 */}
      {edition === 'teacher' && similar_phrases && similar_phrases.length > 0 && (
        <div className="similar-phrases" style={{ marginBottom: 8 }}>
          <Text type="secondary" style={{ marginRight: 8 }}>相似短语：</Text>
          <Space wrap size={[4, 4]}>
            {similar_phrases.map((p, idx) => (
              <Tag key={idx} color="default">{p}</Tag>
            ))}
          </Space>
        </div>
      )}

      {/* 教师版：出现记录（直接展开） */}
      {edition === 'teacher' && occurrences && occurrences.length > 0 && (
        <div style={{ marginTop: 8, fontSize: '10pt' }}>
          <Text type="secondary" style={{ display: 'block', marginBottom: 8 }}>
            出现记录 ({occurrences.length})：
          </Text>
          {occurrences.map((occ, occIdx) => (
            <div key={occIdx} style={{ marginBottom: 8, paddingLeft: 12, borderLeft: '2px solid #d9d9d9' }}>
              <Text type="secondary">{occ.source}</Text>
              <br />
              <Text italic>"{occ.sentence}"</Text>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
