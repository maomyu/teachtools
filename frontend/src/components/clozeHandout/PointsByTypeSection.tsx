/**
 * 考点分类区块组件（带分页）
 *
 * [INPUT]: 依赖 antd, types
 * [OUTPUT]: 对外提供 PointsByTypeSection 组件
 * [POS]: frontend/src/components/clozeHandout 的考点分类组件
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */
import { Typography, Divider, Tag } from 'antd'
import type { PointsByType, WordAnalysisPoint, FixedPhrasePoint, RareMeaningPoint } from '@/types'
import { WordAnalysisTable } from './WordAnalysisTable'
import { FixedPhraseSection } from './FixedPhraseSection'
import { RareMeaningSection } from './RareMeaningSection'

const { Title, Text } = Typography

// ============================================================================
//  分页常量
// ============================================================================

// 词义辨析：每页1个考点词（含4个选项词的三维度表格）
const MAX_WORD_ANALYSIS_PER_PAGE = 1

// 固定搭配：每页最多 6 个
const MAX_FIXED_PHRASE_PER_PAGE = 6

// 熟词僻义：每页最多 4 个（有对比表格）
const MAX_RARE_MEANING_PER_PAGE = 4

// ============================================================================
//  Props 定义
// ============================================================================

interface PointsByTypeSectionProps {
  pointsByType: PointsByType
  edition: 'teacher' | 'student'
}

// ============================================================================
//  主组件：考点分类区块
// ============================================================================

export function PointsByTypeSection({ pointsByType, edition }: PointsByTypeSectionProps) {
  // 从 pointsByType 中获取数据（使用中文字段名）
  const wordAnalysisList = pointsByType['词义辨析'] || []
  const fixedPhraseList = pointsByType['固定搭配'] || []
  const rareMeaningList = pointsByType['熟词僻义'] || []

  return (
    <>
      {/* 词义辨析（分页） */}
      <WordAnalysisPages points={wordAnalysisList} edition={edition} />

      {/* 固定搭配（分页） */}
      <FixedPhrasePages points={fixedPhraseList} edition={edition} />

      {/* 熟词僻义（分页） */}
      <RareMeaningPages points={rareMeaningList} edition={edition} />

      {/* 如果没有任何考点 */}
      {wordAnalysisList.length === 0 && fixedPhraseList.length === 0 && rareMeaningList.length === 0 && (
        <section className="handout-page part-page">
          <Title level={3}>三、考点分类</Title>
          <Divider />
          <Text type="secondary">暂无考点分析数据</Text>
        </section>
      )}
    </>
  )
}

// ============================================================================
//  词义辨析分页组件
// ============================================================================

interface WordAnalysisPagesProps {
  points: WordAnalysisPoint[]
  edition: 'teacher' | 'student'
}

function WordAnalysisPages({ points, edition }: WordAnalysisPagesProps) {
  if (points.length === 0) return null

  // 分页
  const pages: WordAnalysisPoint[][] = []
  for (let i = 0; i < points.length; i += MAX_WORD_ANALYSIS_PER_PAGE) {
    pages.push(points.slice(i, i + MAX_WORD_ANALYSIS_PER_PAGE))
  }

  return (
    <>
      {/* 每个考点词一页 */}
      {pages.map((pagePoints, pageIdx) => {
        return (
          <section key={pageIdx} className="handout-page part-page">
            {pageIdx === 0 && (
              <>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
                  <Title level={3} style={{ margin: 0 }}>三、考点分类——词义辨析</Title>
                  <Tag color="orange">共 {points.length} 个考点词</Tag>
                </div>
                <Divider />
              </>
            )}
            <WordAnalysisTable points={pagePoints} edition={edition} startIndex={pageIdx * MAX_WORD_ANALYSIS_PER_PAGE} />
          </section>
        )
      })}
    </>
  )
}

// ============================================================================
//  固定搭配分页组件
// ============================================================================

interface FixedPhrasePagesProps {
  points: FixedPhrasePoint[]
  edition: 'teacher' | 'student'
}

function FixedPhrasePages({ points, edition }: FixedPhrasePagesProps) {
  if (points.length === 0) return null

  // 分页
  const pages: FixedPhrasePoint[][] = []
  for (let i = 0; i < points.length; i += MAX_FIXED_PHRASE_PER_PAGE) {
    pages.push(points.slice(i, i + MAX_FIXED_PHRASE_PER_PAGE))
  }

  return (
    <>
      {pages.map((pagePoints, pageIdx) => (
        <section key={pageIdx} className="handout-page part-page">
          {pageIdx === 0 ? (
            <>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
                <Title level={3} style={{ margin: 0 }}>考点分类——固定搭配</Title>
                <Tag color="green">共 {points.length} 个考点词</Tag>
              </div>
              <Divider />
            </>
          ) : (
            <>
              <Title level={4}>固定搭配（续 {pageIdx + 1}）</Title>
              <Divider />
            </>
          )}
          <FixedPhraseSection points={pagePoints} edition={edition} startIndex={pageIdx * MAX_FIXED_PHRASE_PER_PAGE} />
        </section>
      ))}
    </>
  )
}

// ============================================================================
//  熟词僻义分页组件
// ============================================================================

interface RareMeaningPagesProps {
  points: RareMeaningPoint[]
  edition: 'teacher' | 'student'
}

function RareMeaningPages({ points, edition }: RareMeaningPagesProps) {
  if (points.length === 0) return null

  // 分页
  const pages: RareMeaningPoint[][] = []
  for (let i = 0; i < points.length; i += MAX_RARE_MEANING_PER_PAGE) {
    pages.push(points.slice(i, i + MAX_RARE_MEANING_PER_PAGE))
  }

  return (
    <>
      {pages.map((pagePoints, pageIdx) => (
        <section key={pageIdx} className="handout-page part-page">
          {pageIdx === 0 ? (
            <>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
                <Title level={3} style={{ margin: 0 }}>考点分类——熟词僻义</Title>
                <Tag color="purple">共 {points.length} 个考点词</Tag>
              </div>
              <Divider />
            </>
          ) : (
            <>
              <Title level={4}>熟词僻义（续 {pageIdx + 1}）</Title>
              <Divider />
            </>
          )}
          <RareMeaningSection points={pagePoints} edition={edition} startIndex={pageIdx * MAX_RARE_MEANING_PER_PAGE} />
        </section>
      ))}
    </>
  )
}
