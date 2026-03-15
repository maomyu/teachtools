/**
 * 词义辨析三维度表格组件
 *
 * [INPUT]: 依赖 antd, types
 * [OUTPUT]: 对外提供 WordAnalysisTable 组件
 * [POS]: frontend/src/components/clozeHandout 的词义辨析表格
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */
import { Typography, Tag, Space } from 'antd'
import type { WordAnalysisPoint } from '@/types'

const { Text, Paragraph } = Typography

// ============================================================================
//  Props 定义
// ============================================================================

interface WordAnalysisTableProps {
  points: WordAnalysisPoint[]
  edition: 'teacher' | 'student'
  startIndex?: number  // 起始序号（用于分页）
}

// ============================================================================
//  主组件：词义辨析三维度表格
// ============================================================================

export function WordAnalysisTable({ points, edition, startIndex = 0 }: WordAnalysisTableProps) {
  if (!points || points.length === 0) {
    return <Text type="secondary">暂无词义辨析数据</Text>
  }

  return (
    <div className="word-analysis-section">
      {points.map((point, idx) => (
        <WordAnalysisItem
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
//  子组件：单个词义辨析项
// ============================================================================

interface WordAnalysisItemProps {
  point: WordAnalysisPoint
  edition: 'teacher' | 'student'
  index: number
}

function WordAnalysisItem({ point, edition, index }: WordAnalysisItemProps) {
  const { word, frequency, definition, word_analysis, dictionary_source, occurrences } = point

  // 如果没有 word_analysis，显示简单格式
  if (!word_analysis || Object.keys(word_analysis).length === 0) {
    return (
      <div className="word-analysis-item" style={{ marginBottom: 16, padding: '12px 0', borderBottom: '1px dashed #e8e8e8' }}>
        <Space>
          <Text strong style={{ fontSize: 14 }}>{index}. {word}</Text>
          <Tag color="orange">{frequency}次</Tag>
          {dictionary_source && <Tag>{dictionary_source}</Tag>}
        </Space>
        {definition && (
          <Paragraph style={{ marginTop: 8, marginBottom: 0 }}>
            释义：{definition}
          </Paragraph>
        )}
      </div>
    )
  }

  // 有 word_analysis，显示三维度表格
  const analysisEntries = Object.entries(word_analysis)

  return (
    <div className="word-analysis-item" style={{ marginBottom: 24 }}>
      {/* 标题行 */}
      <div style={{ marginBottom: 12 }}>
        <Space>
          <Text strong style={{ fontSize: 14 }}>{index}. {word}</Text>
          <Tag color="orange">{frequency}次</Tag>
          {dictionary_source && <Tag>{dictionary_source}</Tag>}
        </Space>
      </div>

      {/* 三维度分析表格 */}
      <table className="handout-table word-analysis-table" style={{ fontSize: '10pt', tableLayout: 'fixed', width: '100%' }}>
        <thead>
          <tr>
            <th style={{ width: '20%' }}>单词</th>
            <th style={{ width: '20%' }}>释义</th>
            <th style={{ width: '20%' }}>使用对象</th>
            <th style={{ width: '20%' }}>使用场景</th>
            <th style={{ width: '20%' }}>正负态度</th>
          </tr>
        </thead>
        <tbody>
          {analysisEntries.map(([w, data]) => {
            const isCorrect = w === word
            return (
              <tr key={w} className={isCorrect ? 'correct-answer' : ''} style={isCorrect ? { background: '#e6f7ff' } : {}}>
                <td style={{ fontWeight: isCorrect ? 'bold' : 'normal' }}>{w}</td>
                <td>{data.definition || '-'}</td>
                <td>{data.dimensions?.使用对象 || '-'}</td>
                <td>{data.dimensions?.使用场景 || '-'}</td>
                <td>{data.dimensions?.正负态度 || '-'}</td>
              </tr>
            )
          })}
        </tbody>
      </table>

      {/* 教师版：出现记录（直接展开） */}
      {edition === 'teacher' && occurrences && occurrences.length > 0 && (
        <div style={{ marginTop: 16, fontSize: '10pt' }}>
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
