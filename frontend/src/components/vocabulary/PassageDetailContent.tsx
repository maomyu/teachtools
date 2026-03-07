/**
 * 文章详情内容组件（可复用）
 *
 * [INPUT]: 依赖 passageId、可选的高亮词汇和位置
 * [OUTPUT]: 对外提供 PassageDetailContent 组件
 * [POS]: frontend/src/components/vocabulary 的文章详情内容
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */
import { useState, useEffect, useRef, useCallback } from 'react'
import {
  Card,
  List,
  Tag,
  Button,
  Typography,
  Space,
  Spin,
  Empty,
  Descriptions,
  Tabs,
} from 'antd'
import { ArrowLeftOutlined, CheckCircleOutlined, EyeOutlined, EyeInvisibleOutlined } from '@ant-design/icons'

import { getPassage } from '@/services/readingService'
import type { PassageDetail, VocabularyInPassage, VocabularyOccurrence, Question } from '@/types'

const { Text } = Typography

interface PassageDetailContentProps {
  passageId: number
  highlightWord?: string      // 可选：初始高亮的词汇
  charPosition?: number       // 可选：初始滚动位置
  onBack?: () => void         // 可选：返回回调
  showBackButton?: boolean    // 是否显示返回按钮（默认 true）
}

export function PassageDetailContent({
  passageId,
  highlightWord: initialHighlightWord,
  charPosition: initialCharPosition,
  onBack,
  showBackButton = true,
}: PassageDetailContentProps) {
  const contentRef = useRef<HTMLDivElement>(null)

  const [loading, setLoading] = useState(true)
  const [passage, setPassage] = useState<PassageDetail | null>(null)

  // 当前高亮的词汇
  const [highlightedWord, setHighlightedWord] = useState<string | null>(initialHighlightWord || null)
  // 当前高亮位置
  const [highlightPositions, setHighlightPositions] = useState<VocabularyOccurrence[]>([])
  // 当前显示的第几个位置
  const [currentIndex, setCurrentIndex] = useState(0)

  // 加载文章详情
  useEffect(() => {
    setLoading(true)
    getPassage(passageId)
      .then(data => {
        setPassage(data)
        // 如果有初始高亮词汇，找到对应的 occurrences
        if (initialHighlightWord && data.vocabulary) {
          const vocab = data.vocabulary.find(v => v.word.toLowerCase() === initialHighlightWord.toLowerCase())
          if (vocab) {
            setHighlightPositions(vocab.occurrences)
            setHighlightedWord(vocab.word)
          }
        }
      })
      .catch(err => {
        console.error('加载文章失败:', err)
      })
      .finally(() => setLoading(false))
  }, [passageId, initialHighlightWord])

  // 滚动定位 effect - 确保数据加载完成且 DOM 渲染完成后再滚动
  useEffect(() => {
    if (!loading && passage && initialCharPosition !== undefined && highlightPositions.length > 0) {
      // 找到 charPosition 对应的索引
      const targetIndex = highlightPositions.findIndex(
        pos => pos.char_position === initialCharPosition
      )
      if (targetIndex !== -1) {
        setCurrentIndex(targetIndex)
      }

      // 使用双重 requestAnimationFrame 确保 DOM 完全渲染
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          scrollToPosition(initialCharPosition)
        })
      })
    }
  }, [loading, passage, initialCharPosition, highlightPositions])

  // 监听外部 highlightWord 变化
  useEffect(() => {
    if (initialHighlightWord && passage?.vocabulary) {
      const vocab = passage.vocabulary.find(v => v.word.toLowerCase() === initialHighlightWord.toLowerCase())
      if (vocab) {
        setHighlightPositions(vocab.occurrences)
        setHighlightedWord(vocab.word)
        setCurrentIndex(0)
      }
    }
  }, [initialHighlightWord, passage])

  // 点击词汇，定位到原文
  const handleWordClick = useCallback(
    (word: VocabularyInPassage) => {
      setHighlightedWord(word.word)
      setHighlightPositions(word.occurrences)
      setCurrentIndex(0)

      // 滚动到第一个位置
      if (word.occurrences.length > 0) {
        scrollToPosition(word.occurrences[0].char_position)
      }
    },
    []
  )

  // 切换到下一个位置
  const handleNextOccurrence = useCallback(() => {
    if (highlightPositions.length === 0) return

    const nextIndex = (currentIndex + 1) % highlightPositions.length
    setCurrentIndex(nextIndex)
    scrollToPosition(highlightPositions[nextIndex].char_position)
  }, [currentIndex, highlightPositions])

  // 滚动到指定位置
  const scrollToPosition = useCallback((charPosition: number) => {
    if (!contentRef.current) return

    // 查找包含该位置的文本节点
    const walker = document.createTreeWalker(
      contentRef.current,
      NodeFilter.SHOW_TEXT,
      null
    )

    let currentPos = 0
    let node: Node | null
    while ((node = walker.nextNode())) {
      const nodeLength = node.textContent?.length || 0
      if (currentPos + nodeLength > charPosition) {
        // 找到包含目标位置的节点
        const element = node.parentElement
        if (element) {
          element.scrollIntoView({ behavior: 'smooth', block: 'center' })
        }
        break
      }
      currentPos += nodeLength
    }
  }, [])

  // 渲染带高亮的内容
  const renderHighlightedContent = useCallback(() => {
    if (!passage?.content) return null

    if (!highlightedWord || highlightPositions.length === 0) {
      return <span style={{ whiteSpace: 'pre-wrap' }}>{passage.content}</span>
    }

    // 按位置排序（从后往前处理，避免位置偏移）
    const sortedPositions = [...highlightPositions].sort(
      (a, b) => (a.char_position || 0) - (b.char_position || 0)
    )

    // 构建高亮内容
    const parts: React.ReactNode[] = []
    let lastEnd = 0

    sortedPositions.forEach((pos, idx) => {
      const start = pos.char_position || 0
      const end = pos.end_position || start + highlightedWord.length

      // 添加前面的普通文本
      if (start > lastEnd) {
        parts.push(
          <span key={`text-${idx}`}>
            {passage.content.slice(lastEnd, start)}
          </span>
        )
      }

      // 添加高亮文本（当前聚焦的用不同样式）
      const isCurrentFocus = idx === currentIndex
      parts.push(
        <mark
          key={`highlight-${idx}`}
          style={{
            backgroundColor: isCurrentFocus ? '#ffeb3b' : '#fff3cd',
            padding: '0 2px',
            borderRadius: '2px',
            fontWeight: isCurrentFocus ? 'bold' : undefined,
            transition: 'background-color 0.3s',
          }}
        >
          {passage.content.slice(start, end)}
        </mark>
      )

      lastEnd = end
    })

    // 添加最后的普通文本
    if (lastEnd < passage.content.length) {
      parts.push(
        <span key="text-end">
          {passage.content.slice(lastEnd)}
        </span>
      )
    }

    return <span style={{ whiteSpace: 'pre-wrap' }}>{parts}</span>
  }, [passage?.content, highlightedWord, highlightPositions, currentIndex])

  // 清除高亮
  const handleClearHighlight = useCallback(() => {
    setHighlightedWord(null)
    setHighlightPositions([])
    setCurrentIndex(0)
  }, [])

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 60 }}>
        <Spin size="large" />
        <div style={{ marginTop: 16 }}>
          <Text type="secondary">加载文章中...</Text>
        </div>
      </div>
    )
  }

  if (!passage) {
    return <Empty description="文章不存在" />
  }

  // 出处信息
  const source = passage.source

  return (
    <div>
      {/* 顶部导航和信息 */}
      {showBackButton && onBack && (
        <div style={{ marginBottom: 12 }}>
          <Button
            type="text"
            icon={<ArrowLeftOutlined />}
            onClick={onBack}
          >
            返回例句列表
          </Button>
        </div>
      )}

      {/* 文章标题 */}
      <Space style={{ marginBottom: 12 }}>
        <Text strong style={{ fontSize: 16 }}>
          {passage.passage_type}篇 - {passage.primary_topic || '未分类'}
        </Text>
        {passage.topic_verified && (
          <Tag icon={<CheckCircleOutlined />} color="success">
            已校对
          </Tag>
        )}
      </Space>

      {/* 出处信息 */}
      <Card size="small" style={{ marginBottom: 12 }}>
        <Descriptions size="small" column={4}>
          <Descriptions.Item label="年份">{source?.year || '-'}</Descriptions.Item>
          <Descriptions.Item label="区县">{source?.region || '-'}</Descriptions.Item>
          <Descriptions.Item label="年级">{source?.grade || '-'}</Descriptions.Item>
          <Descriptions.Item label="词数">{passage.word_count || '-'}</Descriptions.Item>
        </Descriptions>
      </Card>

      {/* 主内容区：上下布局（在面板内更适合） */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {/* 原文区 */}
        <Card
          size="small"
          title="原文内容"
          extra={
            highlightedWord && (
              <Space>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  "{highlightedWord}" - 第 {currentIndex + 1}/{highlightPositions.length} 处
                </Text>
                <Button size="small" onClick={handleNextOccurrence}>
                  下一处
                </Button>
                <Button size="small" onClick={handleClearHighlight}>
                  清除
                </Button>
              </Space>
            )
          }
        >
          <div
            ref={contentRef}
            style={{
              height: 200,
              overflowY: 'auto',
              padding: '8px 0',
              lineHeight: 1.8,
              fontSize: 14,
            }}
          >
            {renderHighlightedContent()}
          </div>
        </Card>

        {/* 词汇和题目区 */}
        <Card size="small" style={{ flex: 1 }} styles={{ body: { padding: 0 } }}>
          <Tabs
            defaultActiveKey="vocabulary"
            style={{ height: '100%' }}
            items={[
              {
                key: 'vocabulary',
                label: `高频词汇 (${passage.vocabulary?.length || 0})`,
                children: (
                  <div style={{ height: 250, overflowY: 'auto', padding: '0 12px' }}>
                    {passage.vocabulary && passage.vocabulary.length > 0 ? (
                      <List
                        dataSource={passage.vocabulary}
                        renderItem={(item) => (
                          <List.Item
                            onClick={() => handleWordClick(item)}
                            style={{
                              cursor: 'pointer',
                              background: highlightedWord === item.word ? '#e6f7ff' : undefined,
                              padding: '8px 12px',
                              borderRadius: 4,
                            }}
                          >
                            <div style={{ width: '100%' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                                <Text strong style={{ fontSize: 14 }}>{item.word}</Text>
                                <Tag color="blue" style={{ fontSize: 11 }}>{item.occurrences?.length || 0}次</Tag>
                              </div>
                              {item.definition && (
                                <Text type="secondary" style={{ fontSize: 12 }}>
                                  {item.definition}
                                </Text>
                              )}
                            </div>
                          </List.Item>
                        )}
                      />
                    ) : (
                      <Empty description="暂无词汇数据" />
                    )}
                  </div>
                ),
              },
              {
                key: 'questions',
                label: `题目 (${passage.questions?.length || 0})`,
                children: (
                  <div style={{ height: 250, overflowY: 'auto', padding: '0 12px' }}>
                    {passage.questions && passage.questions.length > 0 ? (
                      <Space direction="vertical" style={{ width: '100%' }} size="small">
                        {passage.questions.map((q, idx) => (
                          <QuestionCard key={q.id || idx} question={q} />
                        ))}
                      </Space>
                    ) : (
                      <Empty description="暂无题目数据" />
                    )}
                  </div>
                ),
              },
            ]}
          />
        </Card>
      </div>
    </div>
  )
}

// 题目卡片组件
function QuestionCard({ question }: { question: Question }) {
  const [showAnswer, setShowAnswer] = useState(false)

  return (
    <Card
      size="small"
      style={{ marginBottom: 8 }}
      title={
        <Space>
          <Tag color="blue" style={{ fontSize: 11 }}>Q{question.question_number}</Tag>
          <Text style={{ fontSize: 13 }}>{question.question_text}</Text>
        </Space>
      }
    >
      <Space direction="vertical" style={{ width: '100%' }} size="small">
        {question.options && (
          <div style={{ fontSize: 12 }}>
            {['A', 'B', 'C', 'D'].map((opt) => (
              <div key={opt} style={{ marginBottom: 2, paddingLeft: 4 }}>
                <Text style={{ fontSize: 12 }}>
                  <Text strong>{opt}.</Text> {question.options?.[opt as keyof typeof question.options] || '-'}
                </Text>
              </div>
            ))}
          </div>
        )}

        <Button
          type="link"
          size="small"
          icon={showAnswer ? <EyeInvisibleOutlined /> : <EyeOutlined />}
          onClick={() => setShowAnswer(!showAnswer)}
          style={{ padding: 0, fontSize: 12 }}
        >
          {showAnswer ? '隐藏答案' : '显示答案'}
        </Button>

        {showAnswer && (
          <div style={{
            padding: 8,
            background: '#f6ffed',
            borderLeft: '3px solid #52c41a',
            borderRadius: 4
          }}>
            <Text style={{ fontSize: 12 }}>
              <Text strong type="success">正确答案：</Text>
              <Tag color="success" style={{ fontSize: 11 }}>{question.correct_answer}</Tag>
            </Text>
            {question.answer_explanation && (
              <div style={{ marginTop: 4 }}>
                <Text type="secondary" style={{ fontSize: 12 }}>{question.answer_explanation}</Text>
              </div>
            )}
          </div>
        )}
      </Space>
    </Card>
  )
}
