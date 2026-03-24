/**
 * 讲义详情组件（A4 文档格式）
 *
 * [INPUT]: 依赖 antd、readingService
 * [OUTPUT]: 对外提供 HandoutDetail 组件
 * [POS]: frontend/src/components/handout 的 A4 讲义文档
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */
import { useState, useEffect } from 'react'
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
  PrinterOutlined,
} from '@ant-design/icons'

import { QuestionOptions } from '@/components/common/QuestionOptions'
import { RichTextWithImages } from '@/components/common/RichTextWithImages'
import { getHandoutDetail } from '@/services/readingService'
import type { HandoutDetailResponse, ArticleSource, HandoutVocabulary, HandoutPassage, HandoutQuestion } from '@/types'
import './HandoutDetail.css'

const { Title, Text, Paragraph } = Typography

// ============================================================================
//  Props 定义
// ============================================================================

interface HandoutDetailProps {
  grade: string
  topic: string
  edition: 'teacher' | 'student'
  onBack: () => void
}

// ============================================================================
//  主组件：A4 讲义文档
// ============================================================================

export function HandoutDetail({ grade, topic, edition, onBack }: HandoutDetailProps) {
  const [handout, setHandout] = useState<HandoutDetailResponse | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadHandout()
  }, [grade, topic, edition])

  const loadHandout = async () => {
    try {
      setLoading(true)
      const response = await getHandoutDetail(grade, topic, edition)
      setHandout(response)
    } catch (error) {
      console.error('加载讲义失败:', error)
    } finally {
      setLoading(false)
    }
  }

  const handlePrint = () => {
    window.print()
  }

  // 加载中
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

  // 无数据
  if (!handout) {
    return <Empty description="讲义内容不存在" />
  }

  return (
    <div className="handout-container">
      {/* 操作栏（仅屏幕显示，打印时隐藏）*/}
      <div className="handout-toolbar no-print">
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={onBack}>
            返回主题列表
          </Button>
          <Button icon={<PrinterOutlined />} onClick={handlePrint}>
            打印/导出
          </Button>
        </Space>
        <Tag color={edition === 'teacher' ? 'blue' : 'green'} style={{ fontSize: 14, padding: '4px 12px' }}>
          {edition === 'teacher' ? '教师版' : '学生版'}
        </Tag>
      </div>

      {/* A4 文档内容 */}
      <div className="handout-pages">
        {/* 封面页 */}
        <section className="handout-page cover-page">
          <div className="cover-content">
            <Title level={1} style={{ marginBottom: 24 }}>{grade}阅读 CD篇讲义</Title>
            <Title level={2} style={{ marginBottom: 32, fontWeight: 'normal' }}>主题：{topic}</Title>
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
            <div className="toc-item">
              <Text style={{ fontSize: 16 }}>一、文章来源</Text>
              <Text type="secondary" style={{ fontSize: 14, marginLeft: 16 }}>
                （共 {handout.part1_article_sources.length} 套试卷）
              </Text>
            </div>
            <div className="toc-item">
              <Text style={{ fontSize: 16 }}>二、高频词汇</Text>
              <Text type="secondary" style={{ fontSize: 14, marginLeft: 16 }}>
                （共 {handout.part2_vocabulary.length} 个单词）
              </Text>
            </div>
            <div className="toc-item">
              <Text style={{ fontSize: 16 }}>三、阅读文章</Text>
              <Text type="secondary" style={{ fontSize: 14, marginLeft: 16 }}>
                （共 {handout.part3_passages.length} 篇）
              </Text>
            </div>
          </div>
        </section>

        {/* Part 1: 文章来源 */}
        <section className="handout-page part-page">
          <Title level={2}>一、文章来源</Title>
          <Divider />
          <ArticleSourcesTable
            sources={handout.part1_article_sources}
            grade={grade}
            topic={topic}
          />
        </section>

        {/* Part 2: 高频词汇 */}
        <section className="handout-page part-page">
          <Title level={2}>二、高频词汇</Title>
          <Divider />
          <VocabularyTable vocabulary={handout.part2_vocabulary} />
        </section>

        {/* Part 3: 阅读文章 */}
        {handout.part3_passages.map((passage, index) => (
          <section key={passage.id} className="handout-page passage-page">
            <Title level={2}>三、阅读文章（{index + 1}）</Title>
            <Divider />
            <PassageContent passage={passage} edition={edition} index={index + 1} />
          </section>
        ))}
      </div>
    </div>
  )
}

// ============================================================================
//  子组件：文章来源表格
// ============================================================================

interface ArticleSourcesTableProps {
  sources: ArticleSource[]
  grade: string
  topic: string
}

function ArticleSourcesTable({ sources, grade, topic }: ArticleSourcesTableProps) {
  if (sources.length === 0) {
    return <Text type="secondary">暂无文章来源数据</Text>
  }

  return (
    <table className="handout-table sources-table">
      <thead>
        <tr>
          <th style={{ width: '10%' }}>年级</th>
          <th style={{ width: '12%' }}>主题</th>
          <th style={{ width: '8%' }}>年份</th>
          <th style={{ width: '12%' }}>区县</th>
          <th style={{ width: '12%' }}>考试类型</th>
          <th style={{ width: '8%' }}>学期</th>
          <th style={{ width: '38%' }}>篇目</th>
        </tr>
      </thead>
      <tbody>
        {sources.map((source, idx) => (
          <tr key={idx}>
            <td style={{ textAlign: 'center' }}>{grade}</td>
            <td style={{ textAlign: 'center' }}>{topic}</td>
            <td style={{ textAlign: 'center' }}>{source.year}</td>
            <td>{source.region}</td>
            <td>{source.exam_type}</td>
            <td style={{ textAlign: 'center' }}>{source.semester === '上' ? '上学期' : source.semester === '下' ? '下学期' : source.semester || '-'}</td>
            <td>
              {source.passages.map(p => `${p.type}篇: ${p.title || '无标题'}`).join('；')}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

// ============================================================================
//  子组件：高频词汇表格
// ============================================================================

interface VocabularyTableProps {
  vocabulary: HandoutVocabulary[]
}

function VocabularyTable({ vocabulary }: VocabularyTableProps) {
  if (vocabulary.length === 0) {
    return <Text type="secondary">暂无高频词汇数据</Text>
  }

  return (
    <table className="handout-table vocabulary-table">
      <thead>
        <tr>
          <th style={{ width: '8%' }}>序号</th>
          <th style={{ width: '18%' }}>单词</th>
          <th style={{ width: '15%' }}>音标</th>
          <th style={{ width: '49%' }}>释义</th>
          <th style={{ width: '10%' }}>词频</th>
        </tr>
      </thead>
      <tbody>
        {vocabulary.map((vocab, idx) => (
          <tr key={vocab.id}>
            <td style={{ textAlign: 'center' }}>{idx + 1}</td>
            <td style={{ fontWeight: 'bold' }}>{vocab.word}</td>
            <td>{vocab.phonetic || '-'}</td>
            <td>{vocab.definition || '暂无释义'}</td>
            <td style={{ textAlign: 'center' }}>{vocab.frequency}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

// ============================================================================
//  子组件：文章内容
// ============================================================================

interface PassageContentProps {
  passage: HandoutPassage
  edition: 'teacher' | 'student'
  index: number
}

function PassageContent({ passage, edition, index: _index }: PassageContentProps) {
  const sourceText = passage.source
    ? `${passage.source.year} ${passage.source.region} ${passage.source.exam_type}`
    : '来源未知'

  return (
    <div className="passage-content">
      {/* 文章标题和来源 */}
      <div className="passage-header">
        <Title level={3} style={{ marginBottom: 8 }}>
          {passage.type}篇: {passage.title || '无标题'}
        </Title>
        <Space size="middle" style={{ marginBottom: 16 }}>
          <Text type="secondary">{sourceText}</Text>
          {passage.word_count && (
            <Text type="secondary">词数：{passage.word_count}</Text>
          )}
        </Space>
      </div>

      <Divider />

      {/* 文章正文 */}
      <div className="passage-body">
        {passage.content.split('\n').map((paragraph, pIdx) => (
          <Paragraph key={pIdx} style={{ textIndent: '2em', lineHeight: 2, marginBottom: 16 }}>
            {paragraph}
          </Paragraph>
        ))}
      </div>

      {/* 题目部分 */}
      {passage.questions.length > 0 && (
        <>
          <Divider />
          <div className="questions-section">
            <Title level={4} style={{ marginBottom: 16 }}>题目</Title>
            {passage.questions.map((question, qIdx) => (
              <QuestionItem
                key={qIdx}
                question={question}
                index={qIdx + 1}
                edition={edition}
              />
            ))}
          </div>
        </>
      )}
    </div>
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
