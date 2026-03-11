/**
 * 完形填空详情内容组件
 *
 * [INPUT]: 依赖 clozeId、clozeService
 * [OUTPUT]: 对外提供 ClozeDetailContent 组件
 * [POS]: frontend/src/components/cloze 的完形详情内容
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
  Radio,
} from 'antd'
import { ArrowLeftOutlined, EyeOutlined, EyeInvisibleOutlined } from '@ant-design/icons'

import { getCloze } from '@/services/clozeService'
import type { ClozeDetailResponse, VocabularyInCloze } from '@/types'

const { Text } = Typography

interface ClozeDetailContentProps {
  clozeId: number
  onBack?: () => void
  showBackButton?: boolean
  highlightWord?: string      // 初始高亮词汇
  charPosition?: number       // 初始滚动位置
}

const POINT_TYPE_COLORS: Record<string, string> = {
  '固定搭配': 'green',
  '词义辨析': 'orange',
  '熟词僻义': 'purple',
  '词汇': 'blue',
}

export function ClozeDetailContent({
  clozeId,
  onBack,
  showBackButton = true,
  highlightWord: initialHighlightWord,
  charPosition: initialCharPosition,
}: ClozeDetailContentProps) {
  const contentRef = useRef<HTMLDivElement>(null)
  const [loading, setLoading] = useState(true)
  const [cloze, setCloze] = useState<ClozeDetailResponse | null>(null)
  const [selectedBlank, setSelectedBlank] = useState<number | null>(null)
  const [showAnswer, setShowAnswer] = useState(false)

  // 词汇高亮状态
  const [highlightedWord, setHighlightedWord] = useState<string | null>(null)
  const [highlightPositions, setHighlightPositions] = useState<Array<{ char_position: number; end_position?: number }>>([])
  const [currentHighlightIndex, setCurrentHighlightIndex] = useState(0)

  // 加载数据
  useEffect(() => {
    setLoading(true)
    setShowAnswer(false)
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

  // 分割原文
  const contentParts = useMemo(() => {
    if (!cloze?.content) return []
    return cloze.content.split(/_{2,}(\d+)_{2,}/g)
  }, [cloze?.content])

  // 构建渲染后的纯文本、空格位置映射、以及原始位置到渲染位置的映射
  const renderedTextInfo = useMemo(() => {
    if (!contentParts.length) return { text: '', blankPositions: [], positionMap: [] }

    let text = ''
    const blankPositions: Array<{ start: number; end: number; num: number }> = []
    const positionMap: number[] = []  // positionMap[原始位置] = 渲染后位置

    contentParts.forEach((part, idx) => {
      if (idx % 2 === 1) {
        // 空格部分：__1__ → [1]
        const blankNum = parseInt(part)
        const originalLen = part.length  // e.g. "__1__" = 5
        const start = text.length
        text += `[${blankNum}]`  // e.g. "[1]" = 3
        blankPositions.push({ start, end: text.length, num: blankNum })

        // 记录位置映射（空格位置压缩）
        for (let i = 0; i < originalLen; i++) {
          positionMap.push(start + Math.min(i, 2))  // 最多映射到 [1] 的最后一个字符
        }
      } else {
        // 普通文本：位置一一对应
        for (let i = 0; i < part.length; i++) {
          positionMap.push(text.length + i)
        }
        text += part
      }
    })

    return { text, blankPositions, positionMap }
  }, [contentParts])

  // 滚动定位
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

  // 词汇点击 - 高亮原文（直接在渲染文本中搜索词汇位置）
  const handleWordClick = useCallback((vocab: VocabularyInCloze) => {
    setHighlightedWord(vocab.word)

    // 在渲染后的文本中搜索词汇位置
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
      // 滚动到第一个位置
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

  // 切换到上一个高亮位置
  const handlePrevOccurrence = useCallback(() => {
    if (highlightPositions.length === 0) return

    const prevIndex = currentHighlightIndex === 0
      ? highlightPositions.length - 1
      : currentHighlightIndex - 1
    setCurrentHighlightIndex(prevIndex)
    scrollToPosition(highlightPositions[prevIndex].char_position)
  }, [currentHighlightIndex, highlightPositions, scrollToPosition])

  // 切换到下一个高亮位置
  const handleNextOccurrence = useCallback(() => {
    if (highlightPositions.length === 0) return

    const nextIndex = (currentHighlightIndex + 1) % highlightPositions.length
    setCurrentHighlightIndex(nextIndex)
    scrollToPosition(highlightPositions[nextIndex].char_position)
  }, [currentHighlightIndex, highlightPositions, scrollToPosition])

  // 初始高亮：数据加载完成后触发（确保 renderedTextInfo 已计算）
  useEffect(() => {
    if (!loading && cloze && initialHighlightWord && renderedTextInfo.text) {
      const vocab = cloze.vocabulary?.find(
        v => v.word.toLowerCase() === initialHighlightWord.toLowerCase()
      )
      if (vocab) {
        // 直接在渲染后的文本中搜索词汇位置
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
          setHighlightedWord(vocab.word)
          setHighlightPositions(positions)
          // 不在这里滚动，由独立的滚动 useEffect 处理
        }
      }
    }
  }, [loading, cloze, initialHighlightWord, renderedTextInfo.text])

  // 滚动定位 effect - 点击不同卡片时滚动到对应位置并显示答案
  useEffect(() => {
    if (!loading && cloze && initialCharPosition !== undefined && highlightPositions.length > 0 && renderedTextInfo.positionMap.length > 0) {
      // 将原始位置转换为渲染后位置
      const renderedPos = renderedTextInfo.positionMap[initialCharPosition] ?? initialCharPosition

      // 找到最接近的高亮位置索引
      let targetIndex = 0
      let minDiff = Infinity
      highlightPositions.forEach((pos, idx) => {
        const diff = Math.abs(pos.char_position - renderedPos)
        if (diff < minDiff) {
          minDiff = diff
          targetIndex = idx
        }
      })

      setCurrentHighlightIndex(targetIndex)

      // 找到高亮位置对应的空格编号
      const highlightPos = highlightPositions[targetIndex].char_position
      let targetBlank: number | null = null

      for (const bp of renderedTextInfo.blankPositions) {
        // 如果高亮位置在某个空格内
        if (highlightPos >= bp.start && highlightPos < bp.end) {
          targetBlank = bp.num
          break
        }
        // 如果高亮位置在某个空格之前很近，也选中该空格
        if (highlightPos < bp.start && bp.start - highlightPos < 20) {
          targetBlank = bp.num
          break
        }
      }

      // 如果没有找到，找最近的一个空格
      if (targetBlank === null && renderedTextInfo.blankPositions.length > 0) {
        let closestBlank = renderedTextInfo.blankPositions[0]
        let closestDiff = Math.abs(closestBlank.start - highlightPos)
        for (const bp of renderedTextInfo.blankPositions) {
          const diff = Math.abs(bp.start - highlightPos)
          if (diff < closestDiff) {
            closestDiff = diff
            closestBlank = bp
          }
        }
        targetBlank = closestBlank.num
      }

      // 选中空格并显示答案
      if (targetBlank !== null) {
        setSelectedBlank(targetBlank)
        setShowAnswer(true)
      }

      // 滚动到目标位置
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          scrollToPosition(highlightPositions[targetIndex].char_position)
        })
      })
    }
  }, [loading, cloze, initialCharPosition, highlightPositions, renderedTextInfo])

  // 条件返回放在 hooks 之后
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

  // 辅助函数：渲染文本并处理空格标记
  const renderTextWithBlanks = (
    text: string,
    offset: number,
    blankPositions: Array<{ start: number; end: number; num: number }>
  ): React.ReactNode[] => {
    const result: React.ReactNode[] = []
    let textOffset = 0

    // 查找文本中包含的空格
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
          color={isSelected ? 'blue' : 'default'}
          style={{
            cursor: 'pointer',
            fontSize: 14,
            padding: '2px 8px',
            margin: '0 2px',
          }}
          onClick={() => setSelectedBlank(bp.num)}
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

  // 渲染带高亮的原文
  const renderContent = () => {
    const { text: renderedText, blankPositions } = renderedTextInfo

    // 如果有高亮词汇
    if (highlightedWord && highlightPositions.length > 0) {
      // highlightPositions 已经是渲染后的位置，无需转换
      const renderPositions = highlightPositions.map(pos => ({
        start: pos.char_position,
        end: pos.end_position || pos.char_position + highlightedWord.length
      }))

      // 渲染带高亮的内容
      const result: React.ReactNode[] = []
      let lastEnd = 0

      // 按位置排序
      const sortedPositions = [...renderPositions].sort((a, b) => a.start - b.start)

      sortedPositions.forEach((pos, pIdx) => {
        const { start, end } = pos

        // 渲染 start 之前的文本
        if (start > lastEnd) {
          const beforeText = renderedText.slice(lastEnd, start)
          result.push(...renderTextWithBlanks(beforeText, lastEnd, blankPositions))
        }

        // 渲染高亮文本
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

      // 渲染剩余文本
      if (lastEnd < renderedText.length) {
        const afterText = renderedText.slice(lastEnd)
        result.push(...renderTextWithBlanks(afterText, lastEnd, blankPositions))
      }

      return <div style={{ whiteSpace: 'pre-wrap', lineHeight: 2, fontSize: 15 }}>{result}</div>
    }

    // 无高亮，直接渲染带空格标记的内容
    return (
      <div style={{ whiteSpace: 'pre-wrap', lineHeight: 2, fontSize: 15 }}>
        {contentParts.map((part, idx) => {
          if (idx % 2 === 1) {
            const blankNum = parseInt(part)
            const isSelected = selectedBlank === blankNum

            return (
              <Tag
                key={idx}
                color={isSelected ? 'blue' : 'default'}
                style={{
                  cursor: 'pointer',
                  fontSize: 14,
                  padding: '2px 8px',
                  margin: '0 2px',
                }}
                onClick={() => setSelectedBlank(blankNum)}
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

  const currentPoint = cloze.points?.find(p => p.blank_number === selectedBlank)

  return (
    <div style={{
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
    }}>
      {/* 返回按钮 */}
      {showBackButton && onBack && (
        <Button
          type="text"
          icon={<ArrowLeftOutlined />}
          onClick={onBack}
          size="small"
          style={{ marginBottom: 8, flexShrink: 0 }}
        >
          返回列表
        </Button>
      )}

      {/* 文章信息 */}
      <Card size="small" style={{ marginBottom: 8, flexShrink: 0 }}>
        <Descriptions column={3} size="small">
          <Descriptions.Item label="出处">
            {cloze.source?.year}年 {cloze.source?.region} {cloze.source?.grade}
          </Descriptions.Item>
          <Descriptions.Item label="词数">{cloze.word_count || '-'}</Descriptions.Item>
          <Descriptions.Item label="空格数">{cloze.points?.length || 0}</Descriptions.Item>
          <Descriptions.Item label="主话题">
            {cloze.primary_topic ? (
              <Tag color="blue" style={{ fontSize: 11 }}>{cloze.primary_topic}</Tag>
            ) : '-'}
          </Descriptions.Item>
          <Descriptions.Item label="次话题">
            {cloze.secondary_topics?.map(t => (
              <Tag key={t} style={{ fontSize: 11 }}>{t}</Tag>
            )) || '-'}
          </Descriptions.Item>
        </Descriptions>

        {/* 考点分布 */}
        {Object.keys(cloze.point_distribution || {}).length > 0 && (
          <div style={{ marginTop: 6 }}>
            <Text type="secondary" style={{ fontSize: 12 }}>考点分布：</Text>
            <Space size={4} style={{ marginLeft: 8 }}>
              {Object.entries(cloze.point_distribution).map(([type, count]) => (
                <Tag key={type} color={POINT_TYPE_COLORS[type] || 'default'} style={{ fontSize: 11 }}>
                  {type} ({count})
                </Tag>
              ))}
            </Space>
          </div>
        )}
      </Card>

      {/* 完形原文（支持高亮）- 填充剩余空间 */}
      <Card
        style={{ marginBottom: 8, flex: 1, overflow: 'auto', minHeight: 0 }}
        title={
          <Space>
            <Text strong style={{ fontSize: 13 }}>完形原文</Text>
            {highlightedWord && (
              <>
                <Text type="secondary" style={{ fontSize: 11 }}>
                  "{highlightedWord}"
                </Text>
                <Button size="small" onClick={handleClearHighlight}>
                  清除高亮
                </Button>
              </>
            )}
          </Space>
        }
        size="small"
        style={{ marginBottom: 8 }}
      >
        <div ref={contentRef} style={{ fontSize: 13, lineHeight: 1.7 }}>
          {renderContent()}
        </div>
      </Card>

      {/* 空格选择器（不显示答案） */}
      <Card
        title={<Text strong style={{ fontSize: 13 }}>空格选择</Text>}
        size="small"
        style={{ marginBottom: 8, flexShrink: 0 }}
      >
        <Radio.Group
          value={selectedBlank}
          onChange={(e) => {
            setSelectedBlank(e.target.value)
            setShowAnswer(false)
          }}
          buttonStyle="solid"
        >
          {cloze.points?.map(point => (
            <Radio.Button
              key={point.blank_number}
              value={point.blank_number}
            >
              {point.blank_number}
            </Radio.Button>
          ))}
        </Radio.Group>
      </Card>

      {/* 考点详情 */}
      {currentPoint && (
        <Card
          title={
            <Space>
              <Text strong style={{ fontSize: 13 }}>第 {currentPoint.blank_number} 空考点分析</Text>
              {currentPoint.point_type && (
                <Tag color={POINT_TYPE_COLORS[currentPoint.point_type] || 'default'} style={{ fontSize: 10 }}>
                  {currentPoint.point_type}
                </Tag>
              )}
            </Space>
          }
          size="small"
          style={{ marginBottom: 8, flexShrink: 0 }}
        >
          {/* 选项（默认不标记正确答案） */}
          <div style={{ marginBottom: 8 }}>
            <Text type="secondary" style={{ fontSize: 12 }}>选项：</Text>
            <Space wrap size="small" style={{ marginTop: 4 }}>
              {['A', 'B', 'C', 'D'].map(opt => {
                const optionValue = currentPoint.options?.[opt as keyof typeof currentPoint.options]
                const isCorrect = currentPoint.correct_answer === opt
                return (
                  <Tag
                    key={opt}
                    color={showAnswer && isCorrect ? 'success' : 'default'}
                    style={{
                      fontSize: 12,
                      padding: '2px 8px',
                      border: showAnswer && isCorrect ? '2px solid #52c41a' : undefined,
                    }}
                  >
                    {opt}. {optionValue}
                    {showAnswer && isCorrect && <span style={{ marginLeft: 4 }}>✓</span>}
                  </Tag>
                )
              })}
            </Space>
          </div>

          {/* 显示/隐藏答案按钮 */}
          <Button
            type="link"
            icon={showAnswer ? <EyeInvisibleOutlined /> : <EyeOutlined />}
            onClick={() => setShowAnswer(!showAnswer)}
            style={{ padding: 0, marginBottom: 8, fontSize: 12 }}
          >
            {showAnswer ? '隐藏答案' : '显示答案'}
          </Button>

          {/* 答案解析区域（点击后显示） */}
          {showAnswer && (
            <div style={{
              padding: 8,
              background: '#f6ffed',
              borderLeft: '3px solid #52c41a',
              borderRadius: 4,
              marginBottom: 8
            }}>
              {/* 正确答案 */}
              {currentPoint.correct_word && (
                <div style={{ marginBottom: 4 }}>
                  <Text strong type="success" style={{ fontSize: 12 }}>正确答案：</Text>
                  <Tag color="success" style={{ fontSize: 11, marginLeft: 4 }}>
                    {currentPoint.correct_answer}. {currentPoint.correct_word}
                  </Tag>
                </div>
              )}

              {/* 词义 */}
              {currentPoint.translation && (
                <div style={{ marginBottom: 4 }}>
                  <Text strong style={{ fontSize: 12 }}>词义：</Text>
                  <Text style={{ fontSize: 12 }}>{currentPoint.translation}</Text>
                </div>
              )}

              {/* 解析 */}
              {currentPoint.explanation && (
                <div>
                  <Text strong style={{ fontSize: 12 }}>解析：</Text>
                  <Text type="secondary" style={{ fontSize: 12 }}>{currentPoint.explanation}</Text>
                </div>
              )}
            </div>
          )}

          {/* 易混淆词 */}
          {currentPoint.confusion_words && currentPoint.confusion_words.length > 0 && (
            <div style={{ marginTop: 8 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>易混淆词：</Text>
              <List
                size="small"
                dataSource={currentPoint.confusion_words}
                renderItem={(item) => (
                  <List.Item style={{ padding: '4px 0' }}>
                    <Space direction="vertical" size={0}>
                      <Text strong style={{ fontSize: 12 }}>{item.word}</Text>
                      <Text type="secondary" style={{ fontSize: 11 }}>
                        {item.meaning} — {item.reason}
                      </Text>
                    </Space>
                  </List.Item>
                )}
              />
            </div>
          )}
        </Card>
      )}

      {/* 核心词汇（可点击高亮） */}
      {cloze.vocabulary && cloze.vocabulary.length > 0 && (
        <Card
          title={
            <Space>
              <Text strong style={{ fontSize: 13 }}>核心词汇 ({cloze.vocabulary.length})</Text>
              <Text type="secondary" style={{ fontSize: 11 }}>
                点击词汇可在原文中高亮显示
              </Text>
            </Space>
          }
          size="small"
          style={{ marginTop: 8, flexShrink: 0 }}
        >
          <List
            size="small"
            dataSource={[...cloze.vocabulary].sort((a, b) => b.frequency - a.frequency)}
            renderItem={(vocab) => (
              <List.Item
                style={{
                  padding: '4px 0',
                  cursor: 'pointer',
                  background: highlightedWord === vocab.word ? '#e6f7ff' : undefined,
                  borderRadius: 4,
                }}
                onClick={() => handleWordClick(vocab)}
              >
                <div style={{ width: '100%' }}>
                  <Space>
                    <Text strong style={{ fontSize: 13 }}>{vocab.word}</Text>
                    {vocab.definition && (
                      <Text type="secondary" style={{ fontSize: 11 }}>{vocab.definition}</Text>
                    )}
                    <Tag style={{ fontSize: 10 }}>{vocab.frequency}次</Tag>
                  </Space>
                </div>
              </List.Item>
            )}
          />
        </Card>
      )}

      {/* 粘性定位的导航栏 */}
      {highlightedWord && highlightPositions.length > 0 && (
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
