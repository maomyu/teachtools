/**
 * 完形填空详情内容组件
 *
 * [INPUT]: 依赖 clozeId、clozeService
 * [OUTPUT]: 对外提供 ClozeDetailContent 组件
 * [POS]: frontend/src/components/cloze 的完形详情内容
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 *
 * 布局：左右分栏
 * - 左侧：原文（带空格标记）
 * - 右侧：考点分析列表
 * - 底部：核心词汇列表
 */
import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import {
  Card,
  Tag,
  Button,
  Typography,
  Space,
  Spin,
  Empty,
  Descriptions,
  Collapse,
} from 'antd'
import { ArrowLeftOutlined, EyeOutlined, EyeInvisibleOutlined } from '@ant-design/icons'

import { getCloze } from '@/services/clozeService'
import type { ClozeDetailResponse, VocabularyInCloze, ClozePoint } from '@/types'

const { Text } = Typography

// ============================================================================
//  常量定义
// ============================================================================

const POINT_TYPE_COLORS: Record<string, string> = {
  '固定搭配': 'green',
  '词义辨析': 'orange',
  '熟词僻义': 'purple',
  '其他': 'default',
}

// ============================================================================
//  Props 定义
// ============================================================================

interface ClozeDetailContentProps {
  clozeId: number
  onBack?: () => void
  showBackButton?: boolean
  highlightWord?: string      // 初始高亮词汇
  charPosition?: number       // 初始滚动位置
}

// ============================================================================
//  主组件
// ============================================================================

export function ClozeDetailContent({
  clozeId,
  onBack,
  showBackButton = true,
  highlightWord: initialHighlightWord,
  charPosition: _initialCharPosition,
}: ClozeDetailContentProps) {
  // Refs
  const contentRef = useRef<HTMLDivElement>(null)
  const pointListRef = useRef<HTMLDivElement>(null)
  const blankRefs = useRef<Map<number, HTMLSpanElement>>(new Map())
  const pointRefs = useRef<Map<number, HTMLDivElement>>(new Map())

  // 状态
  const [loading, setLoading] = useState(true)
  const [cloze, setCloze] = useState<ClozeDetailResponse | null>(null)
  const [selectedBlank, setSelectedBlank] = useState<number | null>(null)
  const [showAllAnswers, setShowAllAnswers] = useState(false)

  // 词汇高亮状态
  const [highlightedWord, setHighlightedWord] = useState<string | null>(null)
  const [highlightPositions, setHighlightPositions] = useState<Array<{ char_position: number; end_position?: number }>>([])
  const [currentHighlightIndex, setCurrentHighlightIndex] = useState(0)

  // ============================================================================
  //  数据加载
  // ============================================================================

  useEffect(() => {
    setLoading(true)
    setShowAllAnswers(false)
    setHighlightedWord(null)
    getCloze(clozeId)
      .then(data => {
        setCloze(data)
        if (data.points?.length > 0) {
          setSelectedBlank(data.points[0].blank_number || 1)
        }
      })
      .catch(err => {
        console.error('加载完形详情失败:', err)
      })
      .finally(() => setLoading(false))
  }, [clozeId])

  // ============================================================================
  //  文本处理
  // ============================================================================

  // 分割原文
  const contentParts = useMemo(() => {
    if (!cloze?.content) return []
    return cloze.content.split(/_{2,}(\d+)_{2,}/g)
  }, [cloze?.content])

  // 构建渲染后的纯文本、空格位置映射
  const renderedTextInfo = useMemo(() => {
    if (!contentParts.length) return { text: '', blankPositions: [], positionMap: [] }

    let text = ''
    const blankPositions: Array<{ start: number; end: number; num: number }> = []
    const positionMap: number[] = []

    contentParts.forEach((part, idx) => {
      if (idx % 2 === 1) {
        // 空格部分
        const blankNum = parseInt(part)
        const originalLen = part.length
        const start = text.length
        text += `[${blankNum}]`
        blankPositions.push({ start, end: text.length, num: blankNum })

        for (let i = 0; i < originalLen; i++) {
          positionMap.push(start + Math.min(i, 2))
        }
      } else {
        for (let i = 0; i < part.length; i++) {
          positionMap.push(text.length + i)
        }
        text += part
      }
    })

    return { text, blankPositions, positionMap }
  }, [contentParts])

  // ============================================================================
  //  滚动定位
  // ============================================================================

  // 滚动到空格位置
  const scrollToBlank = useCallback((blankNumber: number) => {
    const element = blankRefs.current.get(blankNumber)
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  }, [])

  // 滚动到考点位置
  const scrollToPoint = useCallback((blankNumber: number) => {
    const element = pointRefs.current.get(blankNumber)
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  }, [])

  // 通用滚动定位（用于词汇高亮）
  const scrollToPosition = useCallback((charPosition: number) => {
    if (!contentRef.current) return
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
        const element = node.parentElement
        if (element) {
          element.scrollIntoView({ behavior: 'smooth', block: 'center' })
        }
        break
      }
      currentPos += nodeLength
    }
  }, [])

  // ============================================================================
  //  交互处理
  // ============================================================================

  // 点击空格 → 选中并滚动到考点
  const handleBlankClick = useCallback((blankNumber: number) => {
    setSelectedBlank(blankNumber)
    scrollToPoint(blankNumber)
  }, [scrollToPoint])

  // 点击考点 → 滚动到空格
  const handlePointClick = useCallback((blankNumber: number) => {
    setSelectedBlank(blankNumber)
    scrollToBlank(blankNumber)
  }, [scrollToBlank])

  // 词汇点击 - 高亮原文
  const handleWordClick = useCallback((vocab: VocabularyInCloze) => {
    setHighlightedWord(vocab.word)

    const renderedText = renderedTextInfo.text.toLowerCase()
    const wordLower = vocab.word.toLowerCase()
    const positions: Array<{ char_position: number; end_position: number }> = []

    let searchStart = 0
    while (true) {
      const pos = renderedText.indexOf(wordLower, searchStart)
      if (pos === -1) break
      positions.push({
        char_position: pos,
        end_position: pos + vocab.word.length
      })
      searchStart = pos + 1
    }

    if (positions.length > 0) {
      setHighlightPositions(positions)
      setCurrentHighlightIndex(0)
      setTimeout(() => {
        scrollToPosition(positions[0].char_position)
      }, 100)
    }
  }, [scrollToPosition, renderedTextInfo.text])

  // 清除高亮
  const handleClearHighlight = useCallback(() => {
    setHighlightedWord(null)
    setHighlightPositions([])
    setCurrentHighlightIndex(0)
  }, [])

  // 高亮导航
  const handlePrevOccurrence = useCallback(() => {
    if (highlightPositions.length === 0) return
    const prevIndex = currentHighlightIndex === 0
      ? highlightPositions.length - 1
      : currentHighlightIndex - 1
    setCurrentHighlightIndex(prevIndex)
    scrollToPosition(highlightPositions[prevIndex].char_position)
  }, [currentHighlightIndex, highlightPositions, scrollToPosition])

  const handleNextOccurrence = useCallback(() => {
    if (highlightPositions.length === 0) return
    const nextIndex = (currentHighlightIndex + 1) % highlightPositions.length
    setCurrentHighlightIndex(nextIndex)
    scrollToPosition(highlightPositions[nextIndex].char_position)
  }, [currentHighlightIndex, highlightPositions, scrollToPosition])

  // ============================================================================
  //  渲染函数
  // ============================================================================

  // 渲染带高亮的原文
  const renderContent = () => {
    const { text: renderedText, blankPositions } = renderedTextInfo

    // 有高亮词汇
    if (highlightedWord && highlightPositions.length > 0) {
      const renderPositions = highlightPositions.map(pos => ({
        start: pos.char_position,
        end: pos.end_position || pos.char_position + highlightedWord.length
      }))

      const result: React.ReactNode[] = []
      let lastEnd = 0
      const sortedPositions = [...renderPositions].sort((a, b) => a.start - b.start)

      sortedPositions.forEach((pos, pIdx) => {
        const { start, end } = pos

        if (start > lastEnd) {
          const beforeText = renderedText.slice(lastEnd, start)
          result.push(...renderTextWithBlanks(beforeText, lastEnd, blankPositions))
        }

        const highlightText = renderedText.slice(start, end)
        const isCurrentFocus = pIdx === currentHighlightIndex
        result.push(
          <mark
            key={`highlight-${pIdx}`}
            style={{
              backgroundColor: isCurrentFocus ? '#ffeb3b' : '#fff3cd',
              padding: '0 2px',
              borderRadius: '2px',
              fontWeight: isCurrentFocus ? 'bold' : undefined,
            }}
          >
            {highlightText}
          </mark>
        )

        lastEnd = end
      })

      if (lastEnd < renderedText.length) {
        const afterText = renderedText.slice(lastEnd)
        result.push(...renderTextWithBlanks(afterText, lastEnd, blankPositions))
      }

      return <div style={{ whiteSpace: 'pre-wrap', lineHeight: 2.2, fontSize: 15 }}>{result}</div>
    }

    // 无高亮
    return (
      <div style={{ whiteSpace: 'pre-wrap', lineHeight: 2.2, fontSize: 15 }}>
        {contentParts.map((part, idx) => {
          if (idx % 2 === 1) {
            const blankNum = parseInt(part)
            const isSelected = selectedBlank === blankNum

            return (
              <Tag
                key={idx}
                ref={(el) => {
                  if (el) blankRefs.current.set(blankNum, el)
                }}
                color={isSelected ? 'blue' : 'default'}
                style={{
                  cursor: 'pointer',
                  fontSize: 14,
                  padding: '2px 10px',
                  margin: '0 2px',
                  transition: 'all 0.2s',
                }}
                onClick={() => handleBlankClick(blankNum)}
              >
                {blankNum}
              </Tag>
            )
          }
          return <span key={idx}>{part}</span>
        })}
      </div>
    )
  }

  // 辅助函数：渲染文本并处理空格标记
  const renderTextWithBlanks = (
    text: string,
    offset: number,
    blankPositions: Array<{ start: number; end: number; num: number }>
  ): React.ReactNode[] => {
    const result: React.ReactNode[] = []
    let textOffset = 0

    const relevantBlanks = blankPositions.filter(
      bp => bp.start >= offset && bp.end <= offset + text.length
    )

    if (relevantBlanks.length === 0) {
      return [<span key={`text-${offset}`}>{text}</span>]
    }

    relevantBlanks.forEach((bp, idx) => {
      const localStart = bp.start - offset
      const localEnd = bp.end - offset

      if (localStart > textOffset) {
        result.push(
          <span key={`text-${offset}-${idx}`}>
            {text.slice(textOffset, localStart)}
          </span>
        )
      }

      const isSelected = selectedBlank === bp.num
      result.push(
        <Tag
          key={`blank-${bp.num}-${idx}`}
          ref={(el) => {
            if (el) blankRefs.current.set(bp.num, el)
          }}
          color={isSelected ? 'blue' : 'default'}
          style={{
            cursor: 'pointer',
            fontSize: 14,
            padding: '2px 10px',
            margin: '0 2px',
          }}
          onClick={() => handleBlankClick(bp.num)}
        >
          {bp.num}
        </Tag>
      )

      textOffset = localEnd
    })

    if (textOffset < text.length) {
      result.push(
        <span key={`text-${offset}-end`}>{text.slice(textOffset)}</span>
      )
    }

    return result
  }

  // 渲染单个考点卡片
  const renderPointCard = (point: ClozePoint, index: number) => {
    const blankNum = point.blank_number ?? (index + 1)
    const isSelected = selectedBlank === blankNum
    const pointType = point.point_type || '其他'

    return (
      <div
        key={blankNum}
        ref={(el) => {
          if (el) pointRefs.current.set(blankNum, el)
        }}
        onClick={() => handlePointClick(blankNum)}
        style={{
          padding: '12px 16px',
          marginBottom: 8,
          background: isSelected ? '#e6f7ff' : '#fafafa',
          border: isSelected ? '2px solid #1890ff' : '1px solid #f0f0f0',
          borderRadius: 8,
          cursor: 'pointer',
          transition: 'all 0.2s',
        }}
      >
        {/* 考点标题 */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <Space>
            <Tag color="blue" style={{ fontSize: 13, padding: '2px 8px' }}>
              第 {blankNum} 空
            </Tag>
            <Tag color={POINT_TYPE_COLORS[pointType] || 'default'} style={{ fontSize: 11 }}>
              {pointType}
            </Tag>
          </Space>
          {showAllAnswers && point.correct_answer && (
            <Tag color="success" style={{ fontSize: 12 }}>
              答案: {point.correct_answer}. {point.correct_word}
            </Tag>
          )}
        </div>

        {/* 选项 */}
        <div style={{ marginBottom: 8 }}>
          <Space wrap size={4}>
            {['A', 'B', 'C', 'D'].map(opt => {
              const optionValue = point.options?.[opt as keyof typeof point.options]
              const isCorrect = point.correct_answer === opt
              return (
                <Tag
                  key={opt}
                  color={showAllAnswers && isCorrect ? 'success' : 'default'}
                  style={{
                    fontSize: 12,
                    padding: '2px 8px',
                    border: showAllAnswers && isCorrect ? '2px solid #52c41a' : undefined,
                  }}
                >
                  {opt}. {optionValue}
                </Tag>
              )
            })}
          </Space>
        </div>

        {/* 解析（显示答案时） */}
        {showAllAnswers && (
          <div style={{
            padding: 8,
            background: '#fff',
            borderLeft: '3px solid #52c41a',
            borderRadius: 4,
          }}>
            {point.translation && (
              <div style={{ marginBottom: 4 }}>
                <Text strong style={{ fontSize: 12 }}>词义：</Text>
                <Text style={{ fontSize: 12 }}>{point.translation}</Text>
              </div>
            )}
            {point.explanation && (
              <div>
                <Text strong style={{ fontSize: 12 }}>解析：</Text>
                <Text type="secondary" style={{ fontSize: 12 }}>{point.explanation}</Text>
              </div>
            )}
          </div>
        )}

        {/* 易混淆词 */}
        {showAllAnswers && point.confusion_words && point.confusion_words.length > 0 && (
          <div style={{ marginTop: 8 }}>
            <Text type="secondary" style={{ fontSize: 11 }}>易混淆词：</Text>
            <div style={{ marginTop: 4 }}>
              {point.confusion_words.map((item: { word: string; meaning: string; reason: string }, idx: number) => (
                <div key={idx} style={{ padding: '4px 0', borderBottom: '1px dashed #f0f0f0' }}>
                  <Text strong style={{ fontSize: 11 }}>{item.word}</Text>
                  <Text type="secondary" style={{ fontSize: 11, marginLeft: 8 }}>
                    {item.meaning} — {item.reason}
                  </Text>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    )
  }

  // ============================================================================
  //  初始高亮处理
  // ============================================================================

  useEffect(() => {
    if (!loading && cloze && initialHighlightWord && renderedTextInfo.text) {
      const vocab = cloze.vocabulary?.find(
        v => v.word.toLowerCase() === initialHighlightWord.toLowerCase()
      )
      if (vocab) {
        handleWordClick(vocab)
      }
    }
  }, [loading, cloze, initialHighlightWord, renderedTextInfo.text])

  // ============================================================================
  //  渲染
  // ============================================================================

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 300 }}>
        <Spin size="large" tip="加载中..." />
      </div>
    )
  }

  if (!cloze) {
    return <Empty description="未找到完形文章" />
  }

  return (
    <div style={{
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
    }}>
      {/* 顶部工具栏 */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: 8,
        flexShrink: 0,
      }}>
        <Space>
          {showBackButton && onBack && (
            <Button
              type="text"
              icon={<ArrowLeftOutlined />}
              onClick={onBack}
              size="small"
            >
              返回列表
            </Button>
          )}
          {cloze.source && (
            <Text type="secondary" style={{ fontSize: 12 }}>
              {cloze.source.year} {cloze.source.region} {cloze.source.grade} {cloze.source.exam_type}
            </Text>
          )}
        </Space>
        <Space>
          <Button
            size="small"
            icon={showAllAnswers ? <EyeInvisibleOutlined /> : <EyeOutlined />}
            onClick={() => setShowAllAnswers(!showAllAnswers)}
          >
            {showAllAnswers ? '隐藏答案' : '显示全部答案'}
          </Button>
        </Space>
      </div>

      {/* 文章信息卡片 */}
      <Card size="small" style={{ marginBottom: 8, flexShrink: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Descriptions column={4} size="small">
            <Descriptions.Item label="词数">{cloze.word_count || '-'}</Descriptions.Item>
            <Descriptions.Item label="空格数">{cloze.points?.length || 0}</Descriptions.Item>
            <Descriptions.Item label="话题">
              {cloze.primary_topic ? (
                <Tag color="blue" style={{ fontSize: 11 }}>{cloze.primary_topic}</Tag>
              ) : '-'}
            </Descriptions.Item>
          </Descriptions>
          {/* 考点分布 */}
          {Object.keys(cloze.point_distribution || {}).length > 0 && (
            <Space size={4}>
              {Object.entries(cloze.point_distribution).map(([type, count]) => (
                <Tag key={type} color={POINT_TYPE_COLORS[type] || 'default'} style={{ fontSize: 11 }}>
                  {type} ({count})
                </Tag>
              ))}
            </Space>
          )}
        </div>
      </Card>

      {/* 左右分栏主体 */}
      <div style={{
        flex: 1,
        display: 'flex',
        gap: 12,
        minHeight: 0,
        overflow: 'hidden',
      }}>
        {/* 左侧：原文 */}
        <Card
          style={{
            flex: '1 1 55%',
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column',
          }}
          bodyStyle={{
            flex: 1,
            overflow: 'auto',
            padding: 16,
          }}
          title={
            <Space>
              <Text strong style={{ fontSize: 13 }}>完形原文</Text>
              {highlightedWord && (
                <>
                  <Text type="secondary" style={{ fontSize: 11 }}>
                    "{highlightedWord}"
                  </Text>
                  <Button size="small" onClick={handleClearHighlight}>
                    清除
                  </Button>
                </>
              )}
            </Space>
          }
          size="small"
        >
          <div ref={contentRef}>
            {renderContent()}
          </div>
        </Card>

        {/* 右侧：考点列表 */}
        <Card
          ref={pointListRef}
          style={{
            flex: '1 1 45%',
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column',
          }}
          bodyStyle={{
            flex: 1,
            overflow: 'auto',
            padding: 12,
          }}
          title={
            <Text strong style={{ fontSize: 13 }}>
              考点分析 ({cloze.points?.length || 0})
            </Text>
          }
          size="small"
        >
          <div>
            {cloze.points?.map((point, idx) => renderPointCard(point, idx))}
          </div>
        </Card>
      </div>

      {/* 底部：核心词汇（可折叠） */}
      {cloze.vocabulary && cloze.vocabulary.length > 0 && (
        <Card
          size="small"
          style={{ marginTop: 8, flexShrink: 0 }}
        >
          <Collapse
            ghost
            items={[
              {
                key: 'vocab',
                label: (
                  <Space>
                    <Text strong style={{ fontSize: 13 }}>核心词汇 ({cloze.vocabulary.length})</Text>
                    <Text type="secondary" style={{ fontSize: 11 }}>
                      点击词汇可在原文中高亮
                    </Text>
                  </Space>
                ),
                children: (
                  <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
                    gap: 8,
                  }}>
                    {[...cloze.vocabulary]
                      .sort((a, b) => b.frequency - a.frequency)
                      .map((vocab) => (
                        <div
                          key={vocab.id}
                          onClick={() => handleWordClick(vocab)}
                          style={{
                            padding: '6px 10px',
                            background: highlightedWord === vocab.word ? '#e6f7ff' : '#fafafa',
                            borderRadius: 4,
                            cursor: 'pointer',
                            border: highlightedWord === vocab.word ? '1px solid #1890ff' : '1px solid transparent',
                            transition: 'all 0.2s',
                          }}
                        >
                          <Space>
                            <Text strong style={{ fontSize: 12 }}>{vocab.word}</Text>
                            {vocab.definition && (
                              <Text type="secondary" style={{ fontSize: 11 }}>
                                {vocab.definition.length > 15 ? vocab.definition.slice(0, 15) + '...' : vocab.definition}
                              </Text>
                            )}
                            <Tag style={{ fontSize: 10 }}>{vocab.frequency}次</Tag>
                          </Space>
                        </div>
                      ))}
                  </div>
                ),
              },
            ]}
          />
        </Card>
      )}

      {/* 高亮导航栏 */}
      {highlightedWord && highlightPositions.length > 0 && (
        <div
          style={{
            position: 'sticky',
            bottom: 0,
            background: '#fff',
            padding: '8px 12px',
            borderTop: '1px solid #f0f0f0',
            boxShadow: '0 -2px 8px rgba(0, 0, 0, 0.1)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            zIndex: 100,
            flexShrink: 0,
            marginTop: 8,
          }}
        >
          <Text type="secondary" style={{ fontSize: 12 }}>
            "<Text strong>{highlightedWord}</Text>" - 第 {currentHighlightIndex + 1}/{highlightPositions.length} 处
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
    </div>
  )
}
