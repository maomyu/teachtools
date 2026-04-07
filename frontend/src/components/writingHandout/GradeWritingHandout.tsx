/**
 * 年级作文讲义组件（A4 文档格式）
 *
 * [INPUT]: 依赖 antd、writingService、pdfExport
 * [OUTPUT]: 对外提供 GradeWritingHandout 组件
 * [POS]: frontend/src/components/writingHandout 的年级讲义主组件
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
  Card,
  List,
} from 'antd'
import {
  ArrowLeftOutlined,
  DownloadOutlined,
  FileWordOutlined,
} from '@ant-design/icons'

import { getWritingHandout, getWritingHandoutDocxExportUrl } from '@/services/writingService'
import { exportToPDF } from '@/utils/pdfExport'
import type {
  WritingGradeHandoutResponse,
  WritingHandoutGroup,
  WritingHandoutCategorySection,
  WritingFramework,
  HighFrequencyExpression,
  HandoutSample,
  HighlightedSentence,
} from '@/types'
import '../handout/HandoutDetail.css'

const { Title, Text, Paragraph } = Typography

// ============================================================================
//  A4 分页配置常量
// ============================================================================

// A4 页面可用宽度约为 170mm，每行约 80 个英文字符或 40 个中文字符
// 估算每行字符数
const CHARS_PER_LINE = 70

// 每页最大行数（A4 页面减去标题等，正文区约 45 行）
const MAX_LINES_PER_PAGE = 40

// 高频表达每页最大标签数
const MAX_EXPRESSIONS_PER_PAGE = 24
const SECTION_HEADER_LINES = 4
const SAMPLE_TASK_BLOCK_LINES = 10
const SAMPLE_META_LINES = 2

// 辅助函数：估算段落行数
function estimateLines(text: string): number {
  if (!text) return 0
  // 中文字符算 2 个，英文算 1 个
  const charCount = text.split('').reduce((acc, char) => {
    return acc + (char.charCodeAt(0) > 127 ? 2 : 1)
  }, 0)
  return Math.ceil(charCount / CHARS_PER_LINE)
}

function paginateByLineBudget<T>(
  items: T[],
  estimateFn: (item: T) => number,
  firstPageMaxLines: number,
  continuedPageMaxLines: number = MAX_LINES_PER_PAGE
): T[][] {
  const pages: T[][] = []
  let currentPage: T[] = []
  let currentLines = 0
  let currentLimit = Math.max(1, firstPageMaxLines)

  for (const item of items) {
    const itemLines = Math.max(1, estimateFn(item))
    if (currentPage.length > 0 && currentLines + itemLines > currentLimit) {
      pages.push(currentPage)
      currentPage = []
      currentLines = 0
      currentLimit = continuedPageMaxLines
    }
    currentPage.push(item)
    currentLines += itemLines
  }

  if (currentPage.length > 0) {
    pages.push(currentPage)
  }

  return pages.length > 0 ? pages : [[]]
}

function paginateParagraphs(
  paragraphs: string[],
  firstPageMaxLines: number,
  continuedPageMaxLines: number = MAX_LINES_PER_PAGE
): string[][] {
  return paginateByLineBudget(
    paragraphs,
    (paragraph) => estimateLines(paragraph) + 1,
    firstPageMaxLines,
    continuedPageMaxLines
  )
}

function estimateFrameworkLines(framework: WritingFramework): number {
  let lines = estimateLines(framework.title) + 3
  framework.sections.forEach((section) => {
    lines += estimateLines(section.name) + 1
    if (section.description) {
      lines += estimateLines(section.description) + 1
    }
    if (section.examples.length > 0) {
      section.examples.forEach((example) => {
        lines += estimateLines(example) + 1
      })
    }
    lines += 1
  })
  return lines + 4
}

function estimateHighlightLines(item: HighlightedSentence): number {
  return estimateLines(item.sentence) + estimateLines(`【${item.highlight_type}】${item.explanation}`) + 3
}

// ============================================================================
//  作文讲义专用样式
// ============================================================================

const writingHandoutStyles = `
  .writing-handout-page .ant-card {
    overflow: visible !important;
    word-wrap: break-word;
    word-break: break-word;
  }

  .writing-handout-page .sample-content {
    overflow-wrap: break-word;
    word-wrap: break-word;
    word-break: break-word;
    line-height: 2;
    text-align: justify;
  }

  .writing-handout-page .sample-content p {
    text-indent: 2em;
    margin-bottom: 12px;
  }

  .writing-handout-page .ant-tag {
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    display: inline-block;
    margin: 2px !important;
  }

  .writing-handout-page .expression-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
  }

  .writing-handout-page .highlight-analysis {
    margin-top: 12px;
    padding: 8px;
    background: #f9f9f9;
    border-radius: 4px;
  }

  .writing-handout-page .highlight-item {
    margin-bottom: 8px;
    padding-bottom: 8px;
    border-bottom: 1px dashed #e8e8e8;
  }

  .writing-handout-page .highlight-item:last-child {
    border-bottom: none;
    margin-bottom: 0;
    padding-bottom: 0;
  }
`

// 注入样式
if (typeof document !== 'undefined') {
  const styleId = 'writing-handout-styles'
  if (!document.getElementById(styleId)) {
    const style = document.createElement('style')
    style.id = styleId
    style.textContent = writingHandoutStyles
    document.head.appendChild(style)
  }
}

// ============================================================================
//  Props 定义
// ============================================================================

interface GradeWritingHandoutProps {
  grade: string
  edition: 'teacher' | 'student'
  paperIds?: number[]
  onBack: () => void
}

// ============================================================================
//  主组件：年级作文讲义（A4 文档）
// ============================================================================

export function GradeWritingHandout({ grade, edition, paperIds, onBack }: GradeWritingHandoutProps) {
  const [handout, setHandout] = useState<WritingGradeHandoutResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [exporting, setExporting] = useState(false)
  const contentRef = useRef<HTMLDivElement>(null)
  const flatSections = handout?.groups.flatMap((group) =>
    group.sections.map((section) => ({ group, section }))
  ) ?? []

  useEffect(() => {
    loadHandout()
  }, [grade, edition, paperIds?.join(',')])

  const loadHandout = async () => {
    try {
      setLoading(true)
      const response = await getWritingHandout(grade, edition, paperIds)
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
      const scopeSuffix = paperIds && paperIds.length > 0 ? `_选${paperIds.length}卷` : ''
      const filename = `${grade}作文讲义${scopeSuffix}_${edition === 'teacher' ? '教师版' : '学生版'}_${new Date().toLocaleDateString('zh-CN').replace(/\//g, '-')}`
      await exportToPDF(contentRef.current, filename)
    } finally {
      setExporting(false)
    }
  }

  const handleExportWord = () => {
    const url = getWritingHandoutDocxExportUrl(grade, edition, paperIds)
    const link = document.createElement('a')
    link.href = url
    link.download = ''
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 48 }}>
        <Spin size="large" tip="加载讲义中..." />
      </div>
    )
  }

  if (!handout || handout.groups.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: 48 }}>
        <Empty description="暂无讲义数据" />
        <Button onClick={onBack} style={{ marginTop: 16 }}>返回</Button>
      </div>
    )
  }

  return (
    <div className="handout-container">
      {/* 操作栏（不打印） */}
      <div className="handout-toolbar no-print">
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={onBack}>返回</Button>
          <Button
            type="primary"
            icon={<DownloadOutlined />}
            loading={exporting}
            onClick={handleExport}
          >
            下载 PDF
          </Button>
          <Button icon={<FileWordOutlined />} onClick={handleExportWord}>
            下载 Word
          </Button>
        </Space>
        <Tag color={edition === 'teacher' ? 'blue' : 'green'}>
          {edition === 'teacher' ? '教师版' : '学生版'}
        </Tag>
      </div>

      {/* A4 文档内容 */}
      <div className="handout-pages" ref={contentRef}>
        {/* 封面页 */}
        <section className="handout-page cover-page writing-handout-page">
          <div className="cover-content">
            <Title level={1}>{grade}作文讲义</Title>
            <Divider />
            <Text>包含 {flatSections.length} 个子类 · {handout.total_task_count} 道真题</Text>
            <br />
            <Text type="secondary" style={{ display: 'block', marginTop: 8 }}>
              {paperIds && paperIds.length > 0 ? `已选 ${paperIds.length} 份试卷` : '范围：全年级全部试卷'}
            </Text>
            <br />
            <Text type="secondary">{edition === 'teacher' ? '教师版（含重点句解析）' : '学生版'}</Text>
          </div>
        </section>

        {/* 目录页 */}
        <section className="handout-page toc-page writing-handout-page">
          <Title level={2}>目录</Title>
          <Divider />
          <List
            dataSource={flatSections}
            renderItem={({ group, section }, index) => (
              <List.Item>
                <Text>{index + 1}. {group.group_category.name} / {section.major_category.name} / {section.category.name}</Text>
                <Text type="secondary">（{section.summary.task_count} 题，{section.summary.sample_count} 篇范文）</Text>
              </List.Item>
            )}
          />
        </section>

        {handout.groups.map((group, groupIndex) => (
          <GroupSection
            key={group.group_category.id}
            group={group}
            groupIndex={groupIndex + 1}
            edition={edition}
          />
        ))}
      </div>
    </div>
  )
}

// ============================================================================
//  子组件：单话题讲义区块
// ============================================================================

interface GroupSectionProps {
  group: WritingHandoutGroup
  groupIndex: number
  edition: 'teacher' | 'student'
}

function GroupSection({ group, groupIndex, edition }: GroupSectionProps) {
  return (
    <>
      <section className="handout-page topic-title-page writing-handout-page">
        <Title level={2}>{groupIndex}. {group.group_category.name}</Title>
        <Divider />
        <Text type="secondary">
          共 {group.sections.length} 个子类，覆盖 {group.sections.reduce((sum, section) => sum + section.summary.task_count, 0)} 道题目
        </Text>
      </section>

      {group.sections.map((section, index) => (
        <CategorySection
          key={section.category.id}
          section={section}
          sectionIndex={index + 1}
          edition={edition}
        />
      ))}
    </>
  )
}

interface CategorySectionProps {
  section: WritingHandoutCategorySection
  sectionIndex: number
  edition: 'teacher' | 'student'
}

function CategorySection({ section, sectionIndex, edition }: CategorySectionProps) {
  const { summary, frameworks, expressions, samples, major_category, category, template_content } = section
  const frameworkPages = paginateByLineBudget(
    frameworks,
    estimateFrameworkLines,
    MAX_LINES_PER_PAGE - SECTION_HEADER_LINES
  )
  return (
    <>
      <section className="handout-page topic-title-page writing-handout-page">
        <Title level={2}>{sectionIndex}. {major_category.name} / {category.name}</Title>
        <Divider />
        <Space size="large" wrap>
          <Text>共 {summary.task_count} 道题目</Text>
          <Text>{summary.sample_count} 篇范文</Text>
          {summary.recent_years.length > 0 && (
            <Text type="secondary">
              考查年份：{summary.recent_years.join('、')}
            </Text>
          )}
        </Space>
        {summary.applicable_ranges.length > 0 && (
          <div style={{ marginTop: 16 }}>
            <Text strong>适用题目范围</Text>
            <ul style={{ margin: '8px 0 0 18px' }}>
              {summary.applicable_ranges.map((item, idx) => (
                <li key={idx}><Text>{item}</Text></li>
              ))}
            </ul>
          </div>
        )}
      </section>

      {frameworks.length > 0 && (
        <>
          {frameworkPages.map((frameworkPage, pageIdx) => (
            <section key={pageIdx} className="handout-page part-page writing-handout-page">
              {pageIdx === 0 && (
                <>
                  <Title level={3}>一、写作框架</Title>
                  <Divider />
                </>
              )}
              {pageIdx > 0 && (
                <Text type="secondary" style={{ marginBottom: 16, display: 'block' }}>
                  写作框架（续 {pageIdx}）
                </Text>
              )}
              {frameworkPage.map((framework, idx) => (
                <FrameworkCard key={`${pageIdx}-${idx}`} framework={framework} />
              ))}
            </section>
          ))}
        </>
      )}

      {template_content && (
        <section className="handout-page part-page writing-handout-page">
          <Title level={3}>二、模板原文</Title>
          <Divider />
          <Card size="small" style={{ background: '#fafafa' }}>
            <pre style={{
              margin: 0,
              fontFamily: 'Georgia, "Times New Roman", serif',
              fontSize: 13,
              lineHeight: 1.8,
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              color: '#262626',
            }}>
              {template_content}
            </pre>
          </Card>
        </section>
      )}

      {expressions.length > 0 && (
        <ExpressionPages expressions={expressions} />
      )}

      {samples.map((sample, idx) => (
        <SamplePages
          key={sample.id}
          sample={sample}
          sampleIndex={idx + 1}
          edition={edition}
        />
      ))}
    </>
  )
}

// ============================================================================
//  子组件：写作框架卡片
// ============================================================================

interface FrameworkCardProps {
  framework: WritingFramework
}

function FrameworkCard({ framework }: FrameworkCardProps) {
  return (
    <Card
      size="small"
      title={framework.title}
      style={{ marginBottom: 16 }}
    >
      {framework.sections.map((section, idx) => (
        <div key={idx} style={{ marginBottom: 12 }}>
          <Text strong>{section.name}</Text>
          <Text type="secondary" style={{ marginLeft: 8 }}>{section.description}</Text>
          {section.examples.length > 0 && (
            <ul style={{ margin: '4px 0', paddingLeft: 20 }}>
              {section.examples.map((ex, i) => (
                <li key={i}><Text italic>{ex}</Text></li>
              ))}
            </ul>
          )}
        </div>
      ))}
    </Card>
  )
}

// ============================================================================
//  子组件：高频表达分页
// ============================================================================

interface ExpressionPagesProps {
  expressions: HighFrequencyExpression[]
}

function ExpressionPages({ expressions }: ExpressionPagesProps) {
  // 将所有表达展平并添加分类标签
  const allItems: Array<{ category: string; item: string }> = []
  expressions.forEach(expr => {
    expr.items.forEach(item => {
      allItems.push({ category: expr.category, item })
    })
  })

  // 分页
  const pages: Array<Array<{ category: string; item: string }>> = []
  for (let i = 0; i < allItems.length; i += MAX_EXPRESSIONS_PER_PAGE) {
    pages.push(allItems.slice(i, i + MAX_EXPRESSIONS_PER_PAGE))
  }

  return (
    <>
      {pages.map((pageItems, pageIdx) => (
        <section key={pageIdx} className="handout-page part-page writing-handout-page">
          {pageIdx === 0 && (
            <>
              <Title level={3}>二、高频表达</Title>
              <Divider />
            </>
          )}
          {pageIdx > 0 && (
            <Text type="secondary" style={{ marginBottom: 16, display: 'block' }}>
              高频表达（续 {pageIdx}）
            </Text>
          )}
          <div className="expression-tags">
            {pageItems.map((item, idx) => (
              <Tag key={idx} style={{ margin: '2px 4px' }}>
                <Text type="secondary" style={{ fontSize: 11 }}>[{item.category}]</Text> {item.item}
              </Tag>
            ))}
          </div>
        </section>
      ))}
    </>
  )
}

// ============================================================================
//  子组件：范文多页拆分（基于行数）
// ============================================================================

interface SamplePagesProps {
  sample: HandoutSample
  sampleIndex: number
  edition: 'teacher' | 'student'
}

function SamplePages({ sample, sampleIndex, edition }: SamplePagesProps) {
  // 将范文按段落分割
  const paragraphs = sample.sample_content
    .split('\n')
    .filter(p => p.trim())

  // 如果没有段落，使用原文
  const contentParagraphs = paragraphs.length > 0 ? paragraphs : [sample.sample_content]

  // 估算题目占用的行数（第一页需要预留）
  const taskLines = estimateLines(sample.task_content) + SAMPLE_TASK_BLOCK_LINES
  const firstPageMaxLines = MAX_LINES_PER_PAGE - taskLines - SAMPLE_META_LINES
  const pages = paginateParagraphs(contentParagraphs, firstPageMaxLines)
  const translationParagraphs = (sample.translation || '')
    .split('\n')
    .filter((p: string) => p.trim())
  const translationPages = paginateParagraphs(
    translationParagraphs.length > 0 ? translationParagraphs : [sample.translation || ''],
    MAX_LINES_PER_PAGE - SECTION_HEADER_LINES
  )
  const highlightPages = paginateByLineBudget(
    sample.highlighted_sentences || [],
    estimateHighlightLines,
    MAX_LINES_PER_PAGE - SECTION_HEADER_LINES
  )

  return (
    <>
      {/* 题目页（第一页） */}
      <section className="handout-page part-page writing-handout-page">
        <Title level={3}>三、范文 {sampleIndex}</Title>
        <Divider />

        {/* 来源信息 */}
        {sample.source && (
          <Space style={{ marginBottom: 8 }} wrap>
            {sample.source.year && <Tag color="blue">{sample.source.year}</Tag>}
            {sample.source.region && <Tag>{sample.source.region}</Tag>}
            {sample.source.exam_type && <Tag>{sample.source.exam_type}</Tag>}
          </Space>
        )}

        {/* 题目 */}
        <Card size="small" title="题目" style={{ marginBottom: 12 }}>
          <Paragraph style={{
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
            overflowWrap: 'break-word',
            marginBottom: 0
          }}>
            {sample.task_content}
          </Paragraph>
        </Card>

        {/* 范文正文 - 第一页 */}
        {pages[0] && pages[0].length > 0 && (
          <Card size="small" title="范文">
            <div className="sample-content">
              {pages[0].map((paragraph, pIdx) => (
                <Paragraph key={pIdx} style={{ textIndent: '2em', marginBottom: 12, lineHeight: 2 }}>
                  {paragraph}
                </Paragraph>
              ))}
            </div>

            {/* 字数 */}
            {sample.word_count && (
              <Text type="secondary" style={{ marginTop: 8, display: 'block' }}>
                字数：{sample.word_count} 词
              </Text>
            )}
          </Card>
        )}
      </section>

      {/* 范文续页（如果有更多内容） */}
      {pages.slice(1).map((pageParagraphs, pageIdx) => (
        <section key={pageIdx} className="handout-page part-page writing-handout-page">
          <Text type="secondary" style={{ marginBottom: 16, display: 'block' }}>
            范文 {sampleIndex}（续 {pageIdx + 1}）
          </Text>
          <div className="sample-content">
            {pageParagraphs.map((paragraph, pIdx) => (
              <Paragraph key={pIdx} style={{ textIndent: '2em', marginBottom: 12, lineHeight: 2 }}>
                {paragraph}
              </Paragraph>
            ))}
          </div>
        </section>
      ))}

      {/* 教师版：中文翻译（单独一页） */}
      {edition === 'teacher' && sample.translation && (
        <>
          {translationPages.map((translationPage, pageIdx) => (
            <section key={pageIdx} className="handout-page part-page writing-handout-page">
              {pageIdx === 0 ? (
                <>
                  <Title level={4}>范文 {sampleIndex} - 中文翻译</Title>
                  <Divider />
                </>
              ) : (
                <Text type="secondary" style={{ marginBottom: 16, display: 'block' }}>
                  范文 {sampleIndex} - 中文翻译（续 {pageIdx}）
                </Text>
              )}
              <div className="sample-content" style={{ color: '#333' }}>
                {translationPage.map((paragraph: string, pIdx: number) => (
                  <Paragraph key={pIdx} style={{ textIndent: '2em', marginBottom: 12, lineHeight: 2 }}>
                    {paragraph}
                  </Paragraph>
                ))}
              </div>
            </section>
          ))}
        </>
      )}

      {/* 教师版：重点句解析（单独一页） */}
      {edition === 'teacher' && sample.highlighted_sentences && sample.highlighted_sentences.length > 0 && (
        <>
          {highlightPages.map((highlightPage, pageIdx) => (
            <section key={pageIdx} className="handout-page part-page writing-handout-page">
              {pageIdx === 0 ? (
                <>
                  <Title level={4}>范文 {sampleIndex} - 重点句解析</Title>
                  <Divider />
                </>
              ) : (
                <Text type="secondary" style={{ marginBottom: 16, display: 'block' }}>
                  范文 {sampleIndex} - 重点句解析（续 {pageIdx}）
                </Text>
              )}
              <div className="highlight-analysis">
                {highlightPage.map((h, idx) => (
                  <div key={idx} className="highlight-item">
                    <Text mark style={{ wordBreak: 'break-word' }}>{h.sentence}</Text>
                    <br />
                    <Text type="secondary">【{h.highlight_type}】{h.explanation}</Text>
                  </div>
                ))}
              </div>
            </section>
          ))}
        </>
      )}
    </>
  )
}
