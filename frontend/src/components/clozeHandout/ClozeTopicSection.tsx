/**
 * 完形主题区块组件
 *
 * [INPUT]: 依赖 antd, types
 * [OUTPUT]: 对外提供 ClozeTopicSection 组件
 * [POS]: frontend/src/components/clozeHandout 的主题区块组件
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */
import { Typography, Divider, Tag } from 'antd'
import type { ClozeTopicContent } from '@/types'
import { PointsByTypeSection } from './PointsByTypeSection'
import { ClozePassagePages } from './ClozePassagePages'

const { Title, Text, Paragraph } = Typography

// ============================================================================
//  常量：A4 分页配置（复用阅读讲义）
// ============================================================================

const MAX_VOCAB_ROWS_PER_PAGE = 14

// ============================================================================
//  Props 定义
// ============================================================================

interface ClozeTopicSectionProps {
  topicContent: ClozeTopicContent
  edition: 'teacher' | 'student'
  topicIndex: number
}

// ============================================================================
//  主组件：完形主题区块
// ============================================================================

export function ClozeTopicSection({ topicContent, edition, topicIndex }: ClozeTopicSectionProps) {
  const { topic, part1_article_sources, part2_vocabulary, part3_points_by_type, part4_passages } = topicContent

  return (
    <>
      {/* 主题标题页 */}
      <section className="handout-page topic-title-page">
        <Title level={2} style={{ marginBottom: 16 }}>
          主题 {topicIndex}：{topic}
        </Title>
        <Text type="secondary">
          本主题共 {part1_article_sources.length} 套试卷，{part4_passages.length} 篇完形文章
        </Text>
      </section>

      {/* 第一部分：文章来源 */}
      <section className="handout-page part-page">
        <Title level={3}>一、主题文章来源</Title>
        <Divider />
        <ArticleSourcesList sources={part1_article_sources} topic={topic} />
      </section>

      {/* 第二部分：高频词汇（分页） */}
      <VocabularyPages vocabulary={part2_vocabulary} />

      {/* 第三部分：考点分类 */}
      <PointsByTypeSection
        pointsByType={part3_points_by_type}
        edition={edition}
      />

      {/* 第四部分：完形文章 */}
      {part4_passages.map((passage, index) => (
        <ClozePassagePages
          key={passage.id}
          passage={passage}
          edition={edition}
          index={index}
          total={part4_passages.length}
        />
      ))}
    </>
  )
}

// ============================================================================
//  子组件：文章来源列表
// ============================================================================

interface ArticleSourcesListProps {
  sources: Array<{
    year?: number
    region?: string
    exam_type?: string
    semester?: string
  }>
  topic: string
}

function ArticleSourcesList({ sources, topic }: ArticleSourcesListProps) {
  if (sources.length === 0) {
    return <Text type="secondary">暂无文章来源数据</Text>
  }

  return (
    <div>
      <Paragraph style={{ marginBottom: 16, fontWeight: 'bold' }}>
        主题：{topic}
      </Paragraph>
      <Paragraph style={{ marginBottom: 16 }}>
        本主题共 {sources.length} 套试卷
      </Paragraph>
      <div style={{ lineHeight: 2 }}>
        {sources.map((source, idx) => (
          <div key={idx} style={{ marginBottom: 8 }}>
            <Text>
              {source.year} {source.region} {source.exam_type}
              {source.semester ? ` ${source.semester}学期` : ''}
            </Text>
          </div>
        ))}
      </div>
    </div>
  )
}

// ============================================================================
//  子组件：词汇表格分页
// ============================================================================

interface VocabularyPagesProps {
  vocabulary: Array<{
    id: number
    word: string
    definition?: string
    phonetic?: string
    frequency: number
    source_type: 'both' | 'reading' | 'cloze'
  }>
}

function VocabularyPages({ vocabulary }: VocabularyPagesProps) {
  if (vocabulary.length === 0) {
    return (
      <section className="handout-page part-page">
        <Title level={3}>二、主题高频词汇</Title>
        <Divider />
        <Text type="secondary">暂无高频词汇数据</Text>
      </section>
    )
  }

  // 分页
  const pages: typeof vocabulary[] = []
  for (let i = 0; i < vocabulary.length; i += MAX_VOCAB_ROWS_PER_PAGE) {
    pages.push(vocabulary.slice(i, i + MAX_VOCAB_ROWS_PER_PAGE))
  }

  return (
    <>
      {pages.map((pageVocab, pageIdx) => (
        <section key={pageIdx} className="handout-page part-page">
          {pageIdx === 0 ? (
            <>
              <Title level={3}>二、主题高频词汇</Title>
              <Divider />
            </>
          ) : (
            <>
              <Title level={4}>二、主题高频词汇（续 {pageIdx + 1}）</Title>
              <Divider />
            </>
          )}
          <VocabularyTableRows vocabulary={pageVocab} startIndex={pageIdx * MAX_VOCAB_ROWS_PER_PAGE} />
        </section>
      ))}
    </>
  )
}

// ============================================================================
//  子组件：词汇表格行
// ============================================================================

interface VocabularyTableRowsProps {
  vocabulary: Array<{
    id: number
    word: string
    definition?: string
    phonetic?: string
    frequency: number
    source_type: 'both' | 'reading' | 'cloze'
  }>
  startIndex: number
}

function VocabularyTableRows({ vocabulary, startIndex }: VocabularyTableRowsProps) {
  const getSourceTag = (sourceType: string) => {
    switch (sourceType) {
      case 'both':
        return <Tag color="blue">阅读+完形</Tag>
      case 'reading':
        return <Tag color="green">阅读</Tag>
      case 'cloze':
        return <Tag color="orange">完形</Tag>
      default:
        return null
    }
  }

  return (
    <table className="handout-table vocabulary-table">
      <thead>
        <tr>
          <th style={{ width: '6%' }}>序号</th>
          <th style={{ width: '15%' }}>单词</th>
          <th style={{ width: '12%' }}>音标</th>
          <th style={{ width: '47%' }}>释义</th>
          <th style={{ width: '8%' }}>词频</th>
          <th style={{ width: '12%' }}>来源</th>
        </tr>
      </thead>
      <tbody>
        {vocabulary.map((vocab, idx) => (
          <tr key={vocab.id}>
            <td style={{ textAlign: 'center' }}>{startIndex + idx + 1}</td>
            <td style={{ fontWeight: 'bold' }}>{vocab.word}</td>
            <td>{vocab.phonetic || '-'}</td>
            <td>{vocab.definition || '暂无释义'}</td>
            <td style={{ textAlign: 'center' }}>{vocab.frequency}</td>
            <td style={{ textAlign: 'center' }}>{getSourceTag(vocab.source_type)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
