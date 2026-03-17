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
  Popover,
  List,
} from 'antd'
import { ArrowLeftOutlined, EyeOutlined, EyeInvisibleOutlined } from '@ant-design/icons'

import { getCloze, getPointTypesByCategory } from '@/services/clozeService'
import type { ClozeDetailResponse, VocabularyInCloze, ClozePoint, PointType, PointTypeByCategoryResponse } from '@/types'
import { CATEGORY_COLORS, CATEGORY_NAMES } from '@/types'
import { PointTagGroup, PointDetailSection } from './PointTagGroup'
import { BlankTag } from './PointTag'
import styles from './ClozeDetailContent.module.css'

const { Text } = Typography

// ============================================================================
//  常量定义
// ============================================================================

// v1 旧系统颜色（向后兼容）- 用于 ClozePointsPage 等其他地方
export const POINT_TYPE_COLORS_V1: Record<string, string> = {
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
  initialBlankNumber?: number // 初始定位的空格编号
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
  initialBlankNumber,
}: ClozeDetailContentProps) {
  // Refs
  const contentRef = useRef<HTMLDivElement>(null)
  const blankRefs = useRef<Map<number, HTMLSpanElement>>(new Map())

  // 状态
  const [loading, setLoading] = useState(true)
  const [cloze, setCloze] = useState<ClozeDetailResponse | null>(null)
  const [selectedBlank, setSelectedBlank] = useState<number | null>(null)
  const [showAnswerBlanks, setShowAnswerBlanks] = useState<Set<number>>(new Set())

  // 词汇高亮状态
  const [highlightedWord, setHighlightedWord] = useState<string | null>(null)
  const [highlightPositions, setHighlightPositions] = useState<Array<{ char_position: number; end_position?: number }>>([])
  const [currentHighlightIndex, setCurrentHighlightIndex] = useState(0)

  // 考点类型映射（用于从编码获取完整信息）
  const [pointTypeMap, setPointTypeMap] = useState<Map<string, PointType>>(new Map())

  // ============================================================================
  //  数据加载
  // ============================================================================

  // 加载考点类型定义
  useEffect(() => {
    getPointTypesByCategory()
      .then((data: PointTypeByCategoryResponse) => {
        const map = new Map<string, PointType>()
        Object.values(data).flat().forEach(pt => {
          if (pt) map.set(pt.code, pt)
        })
        setPointTypeMap(map)
      })
      .catch(err => {
        console.error('加载考点类型失败:', err)
      })
  }, [])

  useEffect(() => {
    setLoading(true)
    setShowAnswerBlanks(new Set())
    setHighlightedWord(null)
    getCloze(clozeId)
      .then(data => {
        setCloze(data)
        // 如果有初始空格编号，则选中它；否则默认选中第一个
        if (initialBlankNumber) {
          setSelectedBlank(initialBlankNumber)
        } else if (data.points?.length > 0) {
          setSelectedBlank(data.points[0].blank_number || 1)
        }
      })
      .catch(err => {
        console.error('加载完形详情失败:', err)
      })
      .finally(() => setLoading(false))
  }, [clozeId, initialBlankNumber])

  // ============================================================================
  //  文本处理
  // ============================================================================

  // 分割原文 - 支持统一的 (数字) 格式
  const contentParts = useMemo(() => {
    if (!cloze?.content) return []

    // 匹配 (数字) 格式的空格标记
    const BLANK_REGEX = /\((\d+)\)/g
    const result: (string | number)[] = []
    let lastIndex = 0
    let match

    while ((match = BLANK_REGEX.exec(cloze.content)) !== null) {
      // 添加匹配前的文本
      if (match.index > lastIndex) {
        result.push(cloze.content.slice(lastIndex, match.index))
      }
      // 添加空格编号
      result.push(parseInt(match[1]))
      lastIndex = match.index + match[0].length
    }

    // 添加剩余文本
    if (lastIndex < cloze.content.length) {
      result.push(cloze.content.slice(lastIndex))
    }

    return result
  }, [cloze?.content])

  // 构建渲染后的纯文本、空格位置映射
  const renderedTextInfo = useMemo(() => {
    if (!contentParts.length) return { text: '', blankPositions: [], positionMap: [] }

    let text = ''
    const blankPositions: Array<{ start: number; end: number; num: number }> = []
    const positionMap: number[] = []

    contentParts.forEach((part) => {
      if (typeof part === 'number') {
        // 空格部分
        const blankNum = part
        const start = text.length
        text += `[${blankNum}]`
        blankPositions.push({ start, end: text.length, num: blankNum })

        // 位置映射（简化处理）
        for (let i = 0; i < 3; i++) {
          positionMap.push(start + i)
        }
      } else {
        // 文本部分
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

  // 初始空格定位
  useEffect(() => {
    if (!loading && cloze && initialBlankNumber) {
      setTimeout(() => {
        scrollToBlank(initialBlankNumber)
      }, 100)
    }
  }, [loading, cloze, initialBlankNumber, scrollToBlank])

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

  // 切换单个考点答案显示
  const toggleAnswerShow = useCallback((blankNumber: number, e: React.MouseEvent) => {
    e.stopPropagation()
    setShowAnswerBlanks(prev => {
      const newSet = new Set(prev)
      if (newSet.has(blankNumber)) {
        newSet.delete(blankNumber)
      } else {
        newSet.add(blankNumber)
      }
      return newSet
    })
  }, [])

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

  // 渲染考点 Popover 内容
  const renderPointPopover = (point: ClozePoint, blankNum: number) => {
    const showAnswer = showAnswerBlanks.has(blankNum)
    const pointType = point.point_type || '其他'

    // v2 多标签数据
    const primaryPoint = (point as any).primary_point as PointType | undefined
    const secondaryPoints = (point as any).secondary_points || []
    const rejectionPoints = (point as any).rejection_points || []

    return (
      <div style={{ padding: '12px 4px', minWidth: 340, maxWidth: 520, maxHeight: '70vh', overflow: 'auto', overflowX: 'hidden' }}>
        {/* 标题行 - 使用 PointTagGroup */}
        <div style={{ marginBottom: 8 }}>
          <Space wrap align="start">
            <Tag color="blue" style={{ fontSize: 12, padding: '2px 8px' }}>第 {blankNum} 空</Tag>
            {/* 熟词僻义标签（作为附加标签） */}
            {(point as any).is_rare_meaning && (
              <Tag color="purple" style={{ fontSize: 11, padding: '2px 8px', fontWeight: 500 }}>
                熟词僻义
              </Tag>
            )}
            <PointTagGroup
              primaryPoint={primaryPoint}
              secondaryPoints={secondaryPoints}
              maxSecondaryVisible={2}
              size="s"
              showSecondary={!showAnswer}
              pointTypeMap={pointTypeMap}
            />
          </Space>
        </div>

        {/* 选项 */}
        <div style={{ marginBottom: 8, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
          {['A', 'B', 'C', 'D'].map(opt => {
            const optionValue = point.options?.[opt as keyof typeof point.options]
            const isCorrect = point.correct_answer === opt
            return (
              <Tag
                key={opt}
                color={showAnswer && isCorrect ? 'success' : 'default'}
                style={{ fontSize: 12, padding: '2px 6px' }}
              >
                {opt}. {optionValue}
                {showAnswer && isCorrect && point.correct_word && ` (${point.correct_word})`}
              </Tag>
            )
          })}
        </div>

        {/* 显示答案按钮 */}
        <Button
          size="small"
          type={showAnswer ? 'default' : 'primary'}
          ghost={!showAnswer}
          icon={showAnswer ? <EyeInvisibleOutlined /> : <EyeOutlined />}
          onClick={(e) => toggleAnswerShow(blankNum, e)}
          block
        >
          {showAnswer ? '隐藏答案' : '显示答案'}
        </Button>

        {/* 解析（显示答案时） */}
        {showAnswer && (
          <div style={{ marginTop: 10, paddingTop: 8, borderTop: '1px solid #f0f0f0' }}>
            {/* 使用 PointDetailSection 展示完整考点信息 */}
            <PointDetailSection
              primaryPoint={primaryPoint}
              secondaryPoints={secondaryPoints}
              rejectionPoints={rejectionPoints}
              pointTypeMap={pointTypeMap}
            />

            {point.translation && (
              <div style={{ marginBottom: 6 }}>
                <Text strong style={{ fontSize: 13 }}>词义：</Text>
                <Text style={{ fontSize: 13 }}>{point.translation}</Text>
              </div>
            )}
            {point.explanation && (
              <div style={{ marginBottom: 6 }}>
                <Text strong style={{ fontSize: 13 }}>解析：</Text>
                <Text type="secondary" style={{ fontSize: 13 }}>{point.explanation}</Text>
              </div>
            )}

            {/* 易混淆词 */}
            {point.confusion_words && point.confusion_words.length > 0 && (
              <div style={{
                marginTop: 8,
                padding: '8px 10px',
                background: '#fffbe6',
                borderRadius: 6,
                border: '1px solid #ffe58f'
              }}>
                <Text type="secondary" style={{ fontSize: 13, marginBottom: 4, display: 'block' }}>易混淆词：</Text>
                {point.confusion_words.map((item: { word: string; meaning: string; reason: string }, idx: number) => (
                  <div key={idx} style={{ padding: '6px 0', borderBottom: idx < point.confusion_words!.length - 1 ? '1px dashed #e8e8e8' : 'none' }}>
                    <Text strong style={{ fontSize: 13 }}>{item.word}</Text>
                    <Text type="secondary" style={{ fontSize: 13, marginLeft: 8 }}>
                      {item.meaning} — {item.reason}
                    </Text>
                  </div>
                ))}
              </div>
            )}

            {/* 固定搭配专用内容 (v1: 固定搭配, v2: C2) */}
            {(pointType === '固定搭配' || primaryPoint?.code === 'C2') && point.phrase && (
              <div style={{ marginTop: 8, padding: '8px 10px', background: '#f6ffed', borderRadius: 6, border: '1px solid #b7eb8f' }}>
                <Text strong style={{ color: '#52c41a', fontSize: 11 }}>短语：</Text>
                <Text code style={{ fontSize: 11 }}>{point.phrase}</Text>
                {point.similar_phrases && point.similar_phrases.length > 0 && (
                  <div style={{ marginTop: 4 }}>
                    <Text type="secondary" style={{ fontSize: 10 }}>相似短语：</Text>
                    <Space size={4} wrap>
                      {point.similar_phrases.map((phrase: string, i: number) => (
                        <Tag key={i} style={{ fontSize: 10 }}>{phrase}</Tag>
                      ))}
                    </Space>
                  </div>
                )}
              </div>
            )}

            {/* 词义辨析专用内容 - 三维度分析表格 (v1: 词义辨析, v2: D1) */}
            {(pointType === '词义辨析' || primaryPoint?.code === 'D1') && (point as any).word_analysis && (
              <div style={{ marginTop: 8 }}>
                {(point as any).dictionary_source && (
                  <Text type="secondary" style={{ fontSize: 12, marginBottom: 6, display: 'block' }}>
                    📖 词典来源：{(point as any).dictionary_source}
                  </Text>
                )}
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
                    <thead>
                      <tr style={{ background: '#f5f5f5' }}>
                        <th style={{ padding: '5px 8px', border: '1px solid #e8e8e8', whiteSpace: 'nowrap' }}>单词</th>
                        <th style={{ padding: '5px 8px', border: '1px solid #e8e8e8' }}>释义</th>
                        <th style={{ padding: '5px 8px', border: '1px solid #e8e8e8' }}>使用对象</th>
                        <th style={{ padding: '5px 8px', border: '1px solid #e8e8e8' }}>使用场景</th>
                        <th style={{ padding: '5px 8px', border: '1px solid #e8e8e8' }}>正负态度</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries((point as any).word_analysis).map(([word, data]: [string, any]) => (
                        <tr key={word} style={{ background: word === point.correct_word ? '#e6f7ff' : 'white' }}>
                          <td style={{ padding: '5px 8px', border: '1px solid #e8e8e8', whiteSpace: 'nowrap' }}>
                            <Text strong={word === point.correct_word}>{word}</Text>
                          </td>
                          <td style={{ padding: '5px 8px', border: '1px solid #e8e8e8' }}>
                            <Text type="secondary" style={{ fontSize: 11 }}>{data.definition}</Text>
                          </td>
                          <td style={{ padding: '5px 8px', border: '1px solid #e8e8e8' }}>
                            {data.dimensions?.使用对象 || '-'}
                          </td>
                          <td style={{ padding: '5px 8px', border: '1px solid #e8e8e8' }}>
                            {data.dimensions?.使用场景 || '-'}
                          </td>
                          <td style={{ padding: '5px 8px', border: '1px solid #e8e8e8' }}>
                            {data.dimensions?.正负态度 || '-'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* 熟词僻义专用内容 (v1: 熟词僻义, v2: D2) */}
            {(pointType === '熟词僻义' || primaryPoint?.code === 'D2') && (point as any).textbook_meaning && (
              <div style={{ marginTop: 8, padding: '10px 12px', background: '#f9f0ff', borderRadius: 6, border: '1px solid #d3adf7', maxHeight: 280, overflow: 'auto' }}>
                {(point as any).textbook_source && (
                  <div style={{ marginBottom: 6 }}>
                    <Text type="secondary" style={{ fontSize: 12 }}>课本出处：</Text>
                    <Text style={{ fontSize: 12 }}>{(point as any).textbook_source}</Text>
                  </div>
                )}
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, marginBottom: 6 }}>
                  <div style={{ minWidth: 0 }}>
                    <Text type="secondary" style={{ fontSize: 12 }}>课本释义：</Text>
                    <Text style={{ fontSize: 12, wordBreak: 'break-word' }}>{(point as any).textbook_meaning}</Text>
                  </div>
                  <div style={{ minWidth: 0 }}>
                    <Text type="secondary" style={{ fontSize: 12 }}>语境释义：</Text>
                    <Text style={{ fontSize: 12, color: '#722ed1', wordBreak: 'break-word' }}>{(point as any).context_meaning}</Text>
                  </div>
                </div>
                {(point as any).similar_words && (point as any).similar_words.length > 0 && (
                  <div style={{ marginTop: 6 }}>
                    <Text type="secondary" style={{ fontSize: 12 }}>其他熟词僻义示例：</Text>
                    <div style={{ marginTop: 4, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                      {(point as any).similar_words.map((item: { word: string; textbook: string; rare: string }, i: number) => (
                        <Tag key={i} color="purple" style={{ fontSize: 11, marginBottom: 2, whiteSpace: 'normal', height: 'auto', lineHeight: 1.3 }}>
                          {item.word}: {item.textbook} → {item.rare}
                        </Tag>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* 记忆技巧 */}
            {(point as any).tips && (
              <div style={{ marginTop: 8, padding: '6px 10px', background: '#fffbe6', borderRadius: 4 }}>
                <Text type="secondary" style={{ fontSize: 12 }}>💡 {(point as any).tips}</Text>
              </div>
            )}
          </div>
        )}
      </div>
    )
  }

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
          if (typeof part === 'number') {
            const blankNum = part
            const isSelected = selectedBlank === blankNum
            const point = cloze?.points?.find(p => p.blank_number === blankNum)
            const primaryPoint = point ? (point as any).primary_point as PointType | undefined : undefined

            return (
              <Popover
                key={idx}
                content={point ? renderPointPopover(point, blankNum) : null}
                trigger="click"
                placement="bottom"
                arrow={false}
                overlayStyle={{ maxWidth: 520, maxHeight: '70vh' }}
                overlayInnerStyle={{ maxHeight: '70vh', overflow: 'auto' }}
                getPopupContainer={(triggerNode) => triggerNode.parentElement || document.body}
              >
                <span
                  ref={(el) => {
                    if (el) blankRefs.current.set(blankNum, el as unknown as HTMLSpanElement)
                  }}
                >
                  <BlankTag
                    blankNumber={blankNum}
                    point={primaryPoint}
                    selected={isSelected}
                  />
                </span>
              </Popover>
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
      const point = cloze?.points?.find(p => p.blank_number === bp.num)
      const primaryPoint = point ? (point as any).primary_point as PointType | undefined : undefined

      result.push(
        <Popover
          key={`blank-${bp.num}-${idx}`}
          content={point ? renderPointPopover(point, bp.num) : null}
          trigger="click"
          placement="bottom"
          arrow={false}
          overlayStyle={{ maxWidth: 420, maxHeight: '60vh' }}
          overlayInnerStyle={{ maxHeight: '60vh', overflow: 'auto' }}
          getPopupContainer={(triggerNode) => triggerNode.parentElement || document.body}
        >
          <span
            ref={(el) => {
              if (el) blankRefs.current.set(bp.num, el as unknown as HTMLSpanElement)
            }}
          >
            <BlankTag
              blankNumber={bp.num}
              point={primaryPoint}
              selected={isSelected}
            />
          </span>
        </Popover>
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
        <Spin size="large" fullscreen />
      </div>
    )
  }

  if (!cloze) {
    return <Empty description="未找到完形文章" />
  }

  return (
    <div className={styles.container}>
      {/* 顶部工具栏 */}
      <div className={styles.toolbar}>
        <div className={styles.toolbarLeft}>
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
            <Text type="secondary" style={{ fontSize: 13 }}>
              {cloze.source.year} {cloze.source.region} {cloze.source.grade} {cloze.source.exam_type}
            </Text>
          )}
        </div>
      </div>

      {/* 文章信息卡片 */}
      <Card size="small" className={styles.infoCard}>
        <div className={styles.infoCardContent}>
          <Descriptions column={4} size="small">
            <Descriptions.Item label="词数">
              <Text strong>{cloze.word_count || '-'}</Text>
            </Descriptions.Item>
            <Descriptions.Item label="空格数">
              <Text strong>{cloze.points?.length || 0}</Text>
            </Descriptions.Item>
            <Descriptions.Item label="话题">
              {cloze.primary_topic ? (
                <Tag color="blue">{cloze.primary_topic}</Tag>
              ) : '-'}
            </Descriptions.Item>
          </Descriptions>
          {/* 考点分布 - v2 按大类 */}
          {cloze.point_distribution_by_category && Object.keys(cloze.point_distribution_by_category).length > 0 && (
            <Space size={4}>
              {Object.entries(cloze.point_distribution_by_category).map(([category, count]) => (
                <Tag key={category} color={CATEGORY_COLORS[category] || 'default'}>
                  {CATEGORY_NAMES[category] || category} ({count as number})
                </Tag>
              ))}
            </Space>
          )}
          {/* 考点分布 - v1 向后兼容 */}
          {!cloze.point_distribution_by_category && Object.keys(cloze.point_distribution || {}).length > 0 && (
            <Space size={4}>
              {Object.entries(cloze.point_distribution).map(([type, count]) => (
                <Tag key={type} color={POINT_TYPE_COLORS_V1[type] || 'default'}>
                  {type} ({count})
                </Tag>
              ))}
            </Space>
          )}
        </div>
      </Card>

      {/* 上下分栏主体 */}
      <div className={styles.mainContent}>
        {/* 上方：原文 */}
        <Card
          className={styles.passageCard}
          styles={{ body: { padding: 16 } }}
          title={
            <div className={styles.passageCardHeader}>
              <Text strong style={{ fontSize: 14 }}>完形原文</Text>
              {highlightedWord && (
                <>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    "{highlightedWord}"
                  </Text>
                  <Button size="small" onClick={handleClearHighlight}>
                    清除
                  </Button>
                </>
              )}
            </div>
          }
          size="small"
        >
          <div ref={contentRef} className={styles.passageContent}>
            {renderContent()}
          </div>
        </Card>

        {/* 下方：核心词汇列表 */}
        {cloze.vocabulary && cloze.vocabulary.length > 0 && (
          <Card
            className={styles.pointsCard}
            styles={{ body: { padding: '12px 16px' } }}
            size="small"
          >
            <div style={{ fontWeight: 500, marginBottom: 8, fontSize: 14 }}>
              核心词汇 ({cloze.vocabulary.length})
            </div>
            <List
              dataSource={[...cloze.vocabulary].sort((a, b) => b.frequency - a.frequency)}
              renderItem={(vocab) => (
                <List.Item
                  onClick={() => handleWordClick(vocab)}
                  style={{
                    cursor: 'pointer',
                    padding: '6px 8px',
                    borderRadius: 4,
                    background: highlightedWord === vocab.word ? '#e6f7ff' : 'transparent',
                    border: highlightedWord === vocab.word ? '1px solid #91d5ff' : '1px solid transparent',
                    marginBottom: 4,
                  }}
                >
                  <div style={{ width: '100%', display: 'flex', alignItems: 'flex-start', gap: 8 }}>
                    <Text strong style={{ fontSize: 14, minWidth: 80 }}>{vocab.word}</Text>
                    <Tag color="blue" style={{ fontSize: 11, flexShrink: 0 }}>{vocab.frequency}次</Tag>
                    {vocab.definition && (
                      <Text type="secondary" style={{ fontSize: 12, flex: 1 }}>
                        {vocab.definition}
                      </Text>
                    )}
                  </div>
                </List.Item>
              )}
              style={{ maxHeight: 200, overflow: 'auto' }}
            />
          </Card>
        )}
      </div>

      {/* 高亮导航栏 */}
      {highlightedWord && highlightPositions.length > 0 && (
        <div className={styles.highlightNav}>
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
