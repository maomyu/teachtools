/**
 * 年级讲义组件（A4 文档格式）
 *
 * [INPUT]: 依赖 antd、readingService、pdfExport
 * [OUTPUT]: 对外提供 GradeHandout 组件
 * [POS]: frontend/src/components/handout 的年级讲义主组件
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */
import { useState, useEffect, useRef } from 'react'
import {
  Button,
  Space,
  Tag,
  Typography,
  Spin,
  Empty,
  Divider,
} from 'antd'
import {
  ArrowLeftOutlined,
  DownloadOutlined,
} from '@ant-design/icons'

import { QuestionOptions, parseOptionContent } from '@/components/common/QuestionOptions'
import { RichTextWithImages } from '@/components/common/RichTextWithImages'
import { getGradeHandout } from '@/services/readingService'
import { exportToPDF } from '@/utils/pdfExport'
import type {
  GradeHandoutResponse,
  ArticleSource,
  HandoutVocabulary,
  HandoutPassage,
  HandoutQuestion,
  TopicContent,
} from '@/types'
import './HandoutDetail.css'

const { Title, Text, Paragraph } = Typography

// ============================================================================
//  常量：A4 分页配置
// ============================================================================

// 每行字符数（A4 页面可用宽度约 170mm）
const CHARS_PER_LINE = 70

// 每页最大行数（A4 页面减去标题等，正文区约 40 行）
const MAX_LINES_PER_PAGE = 50

// 每页最大词汇行数
const MAX_VOCAB_ROWS_PER_PAGE = 14

// 辅助函数：估算文本行数（中文字符算 2 个，英文算 1 个）
function estimateLines(text: string): number {
  if (!text) return 0
  const charCount = text.split('').reduce((acc, char) => {
    return acc + (char.charCodeAt(0) > 127 ? 2 : 1)
  }, 0)
  return Math.ceil(charCount / CHARS_PER_LINE)
}

// ============================================================================
//  Props 定义
// ============================================================================

interface GradeHandoutProps {
  grade: string
  edition: 'teacher' | 'student'
  onBack: () => void
}

// ============================================================================
//  主组件：年级讲义（A4 文档）
// ============================================================================

export function GradeHandout({ grade, edition, onBack }: GradeHandoutProps) {
  const [handout, setHandout] = useState<GradeHandoutResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [exporting, setExporting] = useState(false)
  const contentRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    loadHandout()
  }, [grade, edition])

  const loadHandout = async () => {
    try {
      setLoading(true)
      const response = await getGradeHandout(grade, edition)
      setHandout(response)
    } catch (error) {
      console.error('加载讲义失败:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleExport = async () => {
    if (!contentRef.current) return
    try {
      setExporting(true)
      const filename = `${grade}阅读CD篇讲义_${edition === 'teacher' ? '教师版' : '学生版'}_${new Date().toLocaleDateString('zh-CN').replace(/\//g, '-')}`
      await exportToPDF(contentRef.current, filename)
    } finally {
      setExporting(false)
    }
  }

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 48 }}>
        <Spin size="large" />
        <div style={{ marginTop: 16 }}>
          <Text type="secondary">加载讲义内容...</Text>
        </div>
      </div>
    )
  }

  if (!handout) {
    return <Empty description="讲义内容不存在" />
  }

  return (
    <div className="handout-container">
      {/* 操作栏 */}
      <div className="handout-toolbar no-print">
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={onBack}>
            返回年级选择
          </Button>
          <Button
            type="primary"
            icon={<DownloadOutlined />}
            loading={exporting}
            onClick={handleExport}
          >
            下载 PDF
          </Button>
        </Space>
        <Tag color={edition === 'teacher' ? 'blue' : 'green'} style={{ fontSize: 14, padding: '4px 12px' }}>
          {edition === 'teacher' ? '教师版' : '学生版'}
        </Tag>
      </div>

      {/* A4 文档内容 */}
      <div ref={contentRef} className="handout-pages">
        {/* 封面页 */}
        <section className="handout-page cover-page">
          <div className="cover-content">
            <Title level={1} style={{ marginBottom: 24 }}>{grade}阅读 CD篇讲义</Title>
            <div style={{ marginTop: 48 }}>
              <Text style={{ fontSize: 18, display: 'block', marginBottom: 16 }}>
                {edition === 'teacher' ? '教师版（含答案）' : '学生版'}
              </Text>
              <Text type="secondary" style={{ fontSize: 14 }}>
                生成日期：{new Date().toLocaleDateString('zh-CN')}
              </Text>
            </div>
          </div>
        </section>

        {/* 目录页 */}
        <section className="handout-page toc-page">
          <Title level={2} style={{ marginBottom: 32 }}>目 录</Title>
          <div className="toc-list">
            {handout.topics.map((t, idx) => (
              <div key={t.topic} className="toc-item" style={{
                display: 'flex',
                justifyContent: 'space-between',
                padding: '12px 0',
                borderBottom: '1px dashed #e8e8e8'
              }}>
                <Text style={{ fontSize: 16 }}>
                  {idx + 1}. {t.topic}
                </Text>
                <Text type="secondary" style={{ fontSize: 14 }}>
                  {t.passage_count} 篇文章
                </Text>
              </div>
            ))}
          </div>
        </section>

        {/* 每个主题的内容 */}
        {handout.content.map((topicContent, topicIdx) => (
          <TopicSection
            key={topicContent.topic}
            topicContent={topicContent}
            edition={edition}
            topicIndex={topicIdx + 1}
          />
        ))}
      </div>
    </div>
  )
}

// ============================================================================
//  子组件：单个主题区块
// ============================================================================

interface TopicSectionProps {
  topicContent: TopicContent
  edition: 'teacher' | 'student'
  topicIndex: number
}

function TopicSection({ topicContent, edition, topicIndex }: TopicSectionProps) {
  const { topic, part1_article_sources, part2_vocabulary, part3_passages } = topicContent

  return (
    <>
      {/* 主题标题页 */}
      <section className="handout-page topic-title-page">
        <Title level={2} style={{ marginBottom: 16 }}>
          主题 {topicIndex}：{topic}
        </Title>
        <Text type="secondary">
          本主题共 {part1_article_sources.length} 套试卷，{part3_passages.length} 篇文章
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

      {/* 第三部分：阅读文章（分页） */}
      {part3_passages.map((passage, index) => (
        <PassagePages
          key={passage.id}
          passage={passage}
          edition={edition}
          index={index}
          total={part3_passages.length}
        />
      ))}
    </>
  )
}

// ============================================================================
//  子组件：文章来源列表
// ============================================================================

interface ArticleSourcesListProps {
  sources: ArticleSource[]
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
  vocabulary: HandoutVocabulary[]
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
  const pages: HandoutVocabulary[][] = []
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
  vocabulary: HandoutVocabulary[]
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

// ============================================================================
//  子组件：文章多页面拆分（基于行数精确分页）
// ============================================================================

interface PassagePagesProps {
  passage: HandoutPassage
  edition: 'teacher' | 'student'
  index: number
  total: number
}

function PassagePages({ passage, edition, index, total }: PassagePagesProps) {
  const sourceText = passage.source
    ? `${passage.source.year} ${passage.source.region} ${passage.source.exam_type}`
    : '来源未知'

  // 基于行数的精确分页
  const paragraphs = passage.content.split('\n').filter(p => p.trim())

  // 第一页预留标题行数（约 10 行）
  const HEADER_LINES = 10
  const pages: { paragraphs: string[]; lines: number }[] = []
  let currentPage: string[] = []
  let currentLines = 0
  let isFirstPage = true

  for (const paragraph of paragraphs) {
    const paragraphLines = estimateLines(paragraph) + 1 // +1 for paragraph spacing
    const pageMaxLines = isFirstPage ? MAX_LINES_PER_PAGE - HEADER_LINES : MAX_LINES_PER_PAGE

    if (currentLines + paragraphLines > pageMaxLines && currentPage.length > 0) {
      // 当前页放不下，开始新页
      pages.push({ paragraphs: currentPage, lines: currentLines })
      currentPage = []
      currentLines = 0
      isFirstPage = false
    }

    currentPage.push(paragraph)
    currentLines += paragraphLines
  }

  // 添加最后一页
  if (currentPage.length > 0) {
    pages.push({ paragraphs: currentPage, lines: currentLines })
  }

  return (
    <>
      {/* 文章正文页面 */}
      {pages.map((page, pageIdx) => (
        <section key={pageIdx} className="handout-page part-page">
          {pageIdx === 0 && (
            <>
              {/* 文章标题（合并为一行） */}
              <Title level={3} style={{ marginBottom: 8 }}>
                三、阅读文章（{index + 1}/{total}）{passage.type}篇{passage.title ? `: ${passage.title}` : ''}
              </Title>
              {/* 来源信息 */}
              <div className="passage-header" style={{ marginBottom: 8 }}>
                <Space size="middle">
                  <Text type="secondary">{sourceText}</Text>
                  {passage.word_count && (
                    <Text type="secondary">词数：{passage.word_count}</Text>
                  )}
                </Space>
              </div>
              <Divider style={{ margin: '12px 0' }} />
            </>
          )}
          {pageIdx > 0 && (
            <Text type="secondary" style={{ marginBottom: 12, display: 'block' }}>
              {passage.type}篇（续 {pageIdx}）
            </Text>
          )}
          {/* 正文 */}
          <div className="passage-body">
            {page.paragraphs.map((paragraph, pIdx) => (
              <Paragraph key={pIdx} style={{ textIndent: '2em', lineHeight: 2, marginBottom: 12 }}>
                {paragraph}
              </Paragraph>
            ))}
          </div>
        </section>
      ))}

      {/* 题目（分页） */}
      {passage.questions.length > 0 && (
        <QuestionsPages questions={passage.questions} edition={edition} />
      )}
    </>
  )
}

// ============================================================================
//  子组件：题目分页（基于行数精确分页）
// ============================================================================

interface QuestionsPagesProps {
  questions: HandoutQuestion[]
  edition: 'teacher' | 'student'
}

// 估算单道题的行数
function estimateQuestionLines(question: HandoutQuestion, edition: 'teacher' | 'student'): number {
  let lines = 0

  // 题干（文本 + 题干配图）
  const parsedQuestionText = parseOptionContent(question.text || '')
  if (parsedQuestionText.text) {
    lines += estimateLines(parsedQuestionText.text) + 2
  } else {
    lines += 2
  }
  if (parsedQuestionText.imageUrls.length || parsedQuestionText.pendingImageCount) {
    lines += (parsedQuestionText.imageUrls.length + parsedQuestionText.pendingImageCount) * 6
  }

  // 选项（图片选项按更高行数估算，避免分页截断）
  if (question.options) {
    for (const optionValue of [
      question.options.A,
      question.options.B,
      question.options.C,
      question.options.D,
    ]) {
      if (!optionValue) continue

      const parsed = parseOptionContent(optionValue)
      if (parsed.text) {
        lines += estimateLines(parsed.text) + 1
      }
      if (parsed.imageUrls.length || parsed.pendingImageCount) {
        lines += (parsed.imageUrls.length + parsed.pendingImageCount) * 6
      }
    }
    lines += 2
  }

  // 教师版：答案和解析（约 4 行）
  if (edition === 'teacher') {
    lines += 2 // 答案行
    if (question.explanation) {
      lines += estimateLines(question.explanation) + 2
    }
  }

  return lines
}

function QuestionsPages({ questions, edition }: QuestionsPagesProps) {
  // 基于行数的精确分页
  const TITLE_LINES = 6 // 标题预留行数
  const pages: { questions: HandoutQuestion[]; startIndex: number }[] = []
  let currentPage: HandoutQuestion[] = []
  let currentLines = 0
  let currentIndex = 0
  let isFirstPage = true

  for (const question of questions) {
    const questionLines = estimateQuestionLines(question, edition)
    const pageMaxLines = isFirstPage ? MAX_LINES_PER_PAGE - TITLE_LINES : MAX_LINES_PER_PAGE

    if (currentLines + questionLines > pageMaxLines && currentPage.length > 0) {
      // 当前页放不下，开始新页
      pages.push({ questions: currentPage, startIndex: currentIndex })
      currentIndex += currentPage.length
      currentPage = []
      currentLines = 0
      isFirstPage = false
    }

    currentPage.push(question)
    currentLines += questionLines
  }

  // 添加最后一页
  if (currentPage.length > 0) {
    pages.push({ questions: currentPage, startIndex: currentIndex })
  }

  return (
    <>
      {pages.map((page, pageIdx) => (
        <section key={pageIdx} className="handout-page part-page">
          {pageIdx === 0 && (
            <>
              <Title level={4} style={{ marginBottom: 16 }}>题目</Title>
              <Divider />
            </>
          )}
          {pageIdx > 0 && (
            <Text type="secondary" style={{ marginBottom: 12, display: 'block' }}>
              题目（续 {pageIdx}）
            </Text>
          )}
          <div className="questions-section">
            {page.questions.map((question, qIdx) => (
              <QuestionItem
                key={qIdx}
                question={question}
                index={page.startIndex + qIdx + 1}
                edition={edition}
              />
            ))}
          </div>
        </section>
      ))}
    </>
  )
}

// ============================================================================
//  子组件：题目项
// ============================================================================

interface QuestionItemProps {
  question: HandoutQuestion
  index: number
  edition: 'teacher' | 'student'
}

function QuestionItem({ question, index, edition }: QuestionItemProps) {
  return (
    <div className="question-item" style={{ marginBottom: 24 }}>
      {/* 题干 */}
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, marginBottom: 12 }}>
        <Text strong style={{ fontSize: 14, lineHeight: 1.7 }}>
          {index}.
        </Text>
        <RichTextWithImages
          value={question.text || '题目内容缺失'}
          fontSize={14}
          imageMaxWidth={320}
          imageMaxHeight={180}
          strong
          textStyle={{ lineHeight: 1.7 }}
          imageAlt={`题目 ${index} 配图`}
          style={{ flex: 1 }}
        />
      </div>

      {/* 选项 */}
      <QuestionOptions
        options={question.options}
        fontSize={14}
        imageMaxWidth={280}
        imageMaxHeight={160}
        optionSpacing={10}
        style={{ paddingLeft: 24 }}
      />

      {/* 教师版显示答案 */}
      {edition === 'teacher' && (question.correct_answer || question.explanation) && (
        <div className="answer-section" style={{
          marginTop: 12,
          padding: '8px 16px',
          background: '#f5f5f5',
          borderRadius: 4,
          borderLeft: '3px solid #1890ff'
        }}>
          <Text strong style={{ color: '#1890ff' }}>
            {question.correct_answer ? `答案：${question.correct_answer}` : '参考答案'}
          </Text>
          {question.explanation && (
            <Paragraph style={{ marginTop: 8, marginBottom: 0, whiteSpace: 'pre-wrap' }}>
              {question.correct_answer ? <Text strong>解析：</Text> : null}
              {question.explanation}
            </Paragraph>
          )}
        </div>
      )}
    </div>
  )
}
