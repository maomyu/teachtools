/**
 * 文章详情内容组件（可复用）
 *
 * [INPUT]: 依赖 passageId、可选的高亮词汇和位置
 * [OUTPUT]: 对外提供 PassageDetailContent 组件
 * [POS]: frontend/src/components/vocabulary 的文章详情内容
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */
import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
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

  // 根据实际 content 重新计算高亮位置（不信任后端数据）
  const getActualPositions = useCallback((content: string, word: string) => {
    const contentLower = content.toLowerCase()
    const wordLower = word.toLowerCase()
    const positions: { start: number; end: number }[] = []
    let searchStart = 0
    while (true) {
      const pos = contentLower.indexOf(wordLower, searchStart)
      if (pos === -1) break
      positions.push({
        start: pos,
        end: pos + word.length,
      })
      searchStart = pos + word.length
    }
    return positions.sort((a, b) => a.start - b.start)
  }, [])

  // 点击词汇，定位到原文
  const handleWordClick = useCallback(
    (word: VocabularyInPassage) => {
      setHighlightedWord(word.word)
      setHighlightPositions(word.occurrences)
      setCurrentIndex(0)

      // 滚动到第一个位置（使用重新计算的位置）
      if (passage?.content) {
        const actualPositions = getActualPositions(passage.content, word.word)
        if (actualPositions.length > 0) {
          scrollToPosition(actualPositions[0].start)
        }
      }
    },
    [passage?.content, getActualPositions]
  )

  // 切换到上一个位置
  const handlePrevOccurrence = useCallback(() => {
    if (!passage?.content || !highlightedWord) return

    const actualPositions = getActualPositions(passage.content, highlightedWord)
    if (actualPositions.length === 0) return

    const prevIndex = currentIndex === 0 ? actualPositions.length - 1 : currentIndex - 1
    setCurrentIndex(prevIndex)
    scrollToPosition(actualPositions[prevIndex].start)
  }, [currentIndex, passage?.content, highlightedWord, getActualPositions])

  // 切换到下一个位置
  const handleNextOccurrence = useCallback(() => {
    if (!passage?.content || !highlightedWord) return

    const actualPositions = getActualPositions(passage.content, highlightedWord)
    if (actualPositions.length === 0) return

    const nextIndex = (currentIndex + 1) % actualPositions.length
    setCurrentIndex(nextIndex)
    scrollToPosition(actualPositions[nextIndex].start)
  }, [currentIndex, passage?.content, highlightedWord, getActualPositions])

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

    // 不信任后端的位置数据，根据实际 content 重新计算
    const content = passage.content
    const actualPositions = getActualPositions(content, highlightedWord)

    if (actualPositions.length === 0) {
      return <span style={{ whiteSpace: 'pre-wrap' }}>{content}</span>
    }

    // 合并重叠的位置区间
    const mergedRanges: { start: number; end: number }[] = []
    for (const pos of actualPositions) {
      const lastRange = mergedRanges[mergedRanges.length - 1]
      if (lastRange && pos.start < lastRange.end) {
        // 重叠：扩展当前区间
        lastRange.end = Math.max(lastRange.end, pos.end)
      } else {
        // 不重叠：新建区间
        mergedRanges.push({ start: pos.start, end: pos.end })
      }
    }

    // 构建高亮内容
    const parts: React.ReactNode[] = []
    let lastEnd = 0

    mergedRanges.forEach((range, rangeIdx) => {
      // 添加前面的普通文本
      if (range.start > lastEnd) {
        parts.push(
          <span key={`text-${rangeIdx}`}>
            {content.slice(lastEnd, range.start)}
          </span>
        )
      }

      // 判断当前区间是否包含聚焦位置（使用合并后区间的索引）
      const isCurrentFocus = rangeIdx === currentIndex
      parts.push(
        <mark
          key={`highlight-${rangeIdx}`}
          style={{
            backgroundColor: isCurrentFocus ? '#ffeb3b' : '#fff3cd',
            padding: '0 2px',
            borderRadius: '2px',
            fontWeight: isCurrentFocus ? 'bold' : undefined,
            transition: 'background-color 0.3s',
          }}
        >
          {content.slice(range.start, range.end)}
        </mark>
      )

      lastEnd = range.end
    })

    // 添加最后的普通文本
    if (lastEnd < content.length) {
      parts.push(
        <span key="text-end">
          {content.slice(lastEnd)}
        </span>
      )
    }

    return <span style={{ whiteSpace: 'pre-wrap' }}>{parts}</span>
  }, [passage?.content, highlightedWord, highlightPositions, currentIndex, getActualPositions])

  // 清除高亮
  const handleClearHighlight = useCallback(() => {
    setHighlightedWord(null)
    setHighlightPositions([])
    setCurrentIndex(0)
  }, [])

  // 计算实际高亮位置总数（用于显示）
  const actualPositionCount = useMemo(() => {
    if (!passage?.content || !highlightedWord) return 0
    return getActualPositions(passage.content, highlightedWord).length
  }, [passage?.content, highlightedWord, getActualPositions])

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
    <div style={{
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
    }}>
      {/* 顶部导航和信息 */}
      {showBackButton && onBack && (
        <div style={{ marginBottom: 8, flexShrink: 0 }}>
          <Button
            type="text"
            icon={<ArrowLeftOutlined />}
            onClick={onBack}
            size="small"
          >
            返回例句列表
          </Button>
        </div>
      )}

      {/* 文章标题 */}
      <Space style={{ marginBottom: 8, flexShrink: 0 }}>
        <Text strong style={{ fontSize: 14 }}>
          {passage.passage_type}篇 - {passage.primary_topic || '未分类'}
        </Text>
        {passage.topic_verified && (
          <Tag icon={<CheckCircleOutlined />} color="success" style={{ fontSize: 10 }}>
            已校对
          </Tag>
        )}
      </Space>

      {/* 出处信息 */}
      <Card size="small" style={{ marginBottom: 8, flexShrink: 0 }}>
        <Descriptions size="small" column={4}>
          <Descriptions.Item label="年份">{source?.year || '-'}</Descriptions.Item>
          <Descriptions.Item label="区县">{source?.region || '-'}</Descriptions.Item>
          <Descriptions.Item label="年级">{source?.grade || '-'}</Descriptions.Item>
          <Descriptions.Item label="词数">{passage.word_count || '-'}</Descriptions.Item>
        </Descriptions>
      </Card>

      {/* 主内容区：上下布局，填充剩余空间 */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, flex: 1, overflow: 'auto', minHeight: 0 }}>
        {/* 原文区 */}
        <Card size="small" title="原文内容">
          <div
            ref={contentRef}
            style={{
              padding: '4px 0',
              lineHeight: 1.7,
              fontSize: 13,
            }}
          >
            {renderHighlightedContent()}
          </div>
        </Card>

        {/* 固定在底部的导航栏 - 使用 sticky 相对于父容器定位 */}
        {highlightedWord && (
          <div
            style={{
              position: 'sticky',
              bottom: 0,
              background: '#fff',
              padding: '8px 12px',
              borderTop: '1px solid #f0f0f0',
              boxShadow: '0 -2px 8px rgba(0, 0, 0, 0.15)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              zIndex: 100,
              marginTop: 8,
            }}
          >
            <Text type="secondary" style={{ fontSize: 12 }}>
              "<Text strong>{highlightedWord}</Text>" - 第 {currentIndex + 1}/{actualPositionCount} 处
            </Text>
            <Space size="small">
              <Button size="small" onClick={handlePrevOccurrence}>
                上一处
              </Button>
              <Button size="small" type="primary" onClick={handleNextOccurrence}>
                下一处
              </Button>
              <Button size="small" onClick={handleClearHighlight}>
                清除
              </Button>
            </Space>
          </div>
        )}

        {/* 词汇和题目区 */}
        <Card size="small" styles={{ body: { padding: 0 } }}>
          <Tabs
            defaultActiveKey="vocabulary"
            items={[
              {
                key: 'vocabulary',
                label: `高频词汇 (${passage.vocabulary?.length || 0})`,
                children: (
                  <div style={{ padding: '0 12px' }}>
                    {passage.vocabulary && passage.vocabulary.length > 0 ? (
                      <List
                        dataSource={[...passage.vocabulary].sort((a, b) => (b.occurrences?.length || 0) - (a.occurrences?.length || 0))}
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
                  <div style={{ padding: '0 12px' }}>
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
