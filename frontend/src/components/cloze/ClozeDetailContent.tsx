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

import { getCloze } from '@/services/clozeService'
import type { ClozeDetailResponse, VocabularyInCloze, ClozePoint } from '@/types'
import { CATEGORY_COLORS as CAT_COLORS, CATEGORY_NAMES, PRIORITY_NAMES } from '@/types'
import styles from './ClozeDetailContent.module.css'

const { Text } = Typography

// ============================================================================
//  常量定义
// ============================================================================

// v1 旧系统颜色（向后兼容）
const POINT_TYPE_COLORS_V1: Record<string, string> = {
  '固定搭配': 'green',
  '词义辨析': 'orange',
  '熟词僻义': 'purple',
  '其他': 'default',
}

// 获取考点标签颜色（兼容新旧两种格式）
const getPointTagColor = (point: ClozePoint): string => {
  // v2: 使用主考点的大类颜色
  if ((point as any).primary_point?.category) {
    return CAT_COLORS[(point as any).primary_point.category] || 'default'
  }
  // v1: 使用旧类型颜色
  return POINT_TYPE_COLORS_V1[point.point_type || '其他'] || 'default'
}

// 获取考点显示名称（兼容新旧两种格式）
const getPointDisplayName = (point: ClozePoint): string => {
  // v2: 使用主考点编码和名称
  if ((point as any).primary_point) {
    const pp = (point as any).primary_point
    return `${pp.code} ${pp.name}`
  }
  // v1: 使用旧类型名称
  return point.point_type || '其他'
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
  const pointListRef = useRef<HTMLDivElement>(null)
  const blankRefs = useRef<Map<number, HTMLSpanElement>>(new Map())
  const pointRefs = useRef<Map<number, HTMLDivElement>>(new Map())

  // 状态
  const [loading, setLoading] = useState(true)
  const [cloze, setCloze] = useState<ClozeDetailResponse | null>(null)
  const [selectedBlank, setSelectedBlank] = useState<number | null>(null)
  const [showAnswerBlanks, setShowAnswerBlanks] = useState<Set<number>>(new Set())

  // 词汇高亮状态
  const [highlightedWord, setHighlightedWord] = useState<string | null>(null)
  const [highlightPositions, setHighlightPositions] = useState<Array<{ char_position: number; end_position?: number }>>([])
  const [currentHighlightIndex, setCurrentHighlightIndex] = useState(0)

  // ============================================================================
  //  数据加载
  // ============================================================================

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
    const primaryPoint = (point as any).primary_point
    const secondaryPoints = (point as any).secondary_points || []
    const rejectionPoints = (point as any).rejection_points || []

    // 获取主考点颜色和名称
    const primaryColor = getPointTagColor(point)
    const primaryName = getPointDisplayName(point)

    return (
      <div style={{ padding: '8px 0', minWidth: 300, maxWidth: 420, maxHeight: '55vh', overflow: 'auto', overflowX: 'hidden' }}>
        {/* 标题行 - v2 多标签 */}
        <div style={{ marginBottom: 8 }}>
          <Space wrap>
            <Tag color="blue" style={{ fontSize: 12, padding: '2px 8px' }}>第 {blankNum} 空</Tag>
            {/* 主考点 */}
            <Tag color={primaryColor} style={{ fontSize: 11 }}>
              {primaryName}
            </Tag>
            {/* 辅助考点标签（最多显示2个） */}
            {secondaryPoints.slice(0, 2).map((sp: any, idx: number) => (
              <Tag key={idx} color="default" style={{ fontSize: 10 }}>
                +{sp.point_code}
              </Tag>
            ))}
            {secondaryPoints.length > 2 && (
              <Tag color="default" style={{ fontSize: 10 }}>+{secondaryPoints.length - 2}</Tag>
            )}
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
            {/* v2 多考点详情 */}
            {primaryPoint && (
              <div style={{ marginBottom: 8, padding: '6px 8px', background: '#f5f5f5', borderRadius: 4 }}>
                <Text strong style={{ fontSize: 11 }}>
                  主考点 ({primaryPoint.code})
                </Text>
                <Text type="secondary" style={{ fontSize: 11, marginLeft: 4 }}>
                  {CATEGORY_NAMES[primaryPoint.category]} · {PRIORITY_NAMES[primaryPoint.priority]}
                </Text>
                {primaryPoint.description && (
                  <div style={{ marginTop: 2 }}>
                    <Text type="secondary" style={{ fontSize: 10 }}>{primaryPoint.description}</Text>
                  </div>
                )}
              </div>
            )}

            {/* 辅助考点列表 */}
            {secondaryPoints.length > 0 && (
              <div style={{ marginBottom: 8, padding: '6px 8px', background: '#fafafa', borderRadius: 4 }}>
                <Text type="secondary" style={{ fontSize: 10, marginBottom: 4, display: 'block' }}>
                  辅助考点：
                </Text>
                {secondaryPoints.map((sp: any, idx: number) => (
                  <Tag key={idx} style={{ fontSize: 10, marginBottom: 2 }}>
                    {sp.point_code}
                    {sp.explanation && `: ${sp.explanation}`}
                  </Tag>
                ))}
              </div>
            )}

            {/* 排错点列表 */}
            {rejectionPoints.length > 0 && (
              <div style={{ marginBottom: 8, padding: '6px 8px', background: '#fff2f0', borderRadius: 4, border: '1px solid #ffccc7' }}>
                <Text type="secondary" style={{ fontSize: 10, marginBottom: 4, display: 'block' }}>
                  排错依据：
                </Text>
                {rejectionPoints.map((rp: any, idx: number) => (
                  <div key={idx} style={{ fontSize: 10, marginBottom: 2 }}>
                    <Text delete type="danger">{rp.option_word}</Text>
                    <Text type="secondary" style={{ marginLeft: 4 }}>
                      ← {rp.point_code}
                      {rp.explanation && `: ${rp.explanation}`}
                    </Text>
                  </div>
                ))}
              </div>
            )}

            {point.translation && (
              <div style={{ marginBottom: 6 }}>
                <Text strong style={{ fontSize: 12 }}>词义：</Text>
                <Text style={{ fontSize: 12 }}>{point.translation}</Text>
              </div>
            )}
            {point.explanation && (
              <div style={{ marginBottom: 6 }}>
                <Text strong style={{ fontSize: 12 }}>解析：</Text>
                <Text type="secondary" style={{ fontSize: 12 }}>{point.explanation}</Text>
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
                <Text type="secondary" style={{ fontSize: 11, marginBottom: 4, display: 'block' }}>易混淆词：</Text>
                {point.confusion_words.map((item: { word: string; meaning: string; reason: string }, idx: number) => (
                  <div key={idx} style={{ padding: '4px 0', borderBottom: idx < point.confusion_words!.length - 1 ? '1px dashed #e8e8e8' : 'none' }}>
                    <Text strong style={{ fontSize: 11 }}>{item.word}</Text>
                    <Text type="secondary" style={{ fontSize: 11, marginLeft: 8 }}>
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
                  <Text type="secondary" style={{ fontSize: 10, marginBottom: 4, display: 'block' }}>
                    词典来源：{(point as any).dictionary_source}
                  </Text>
                )}
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', fontSize: 10, borderCollapse: 'collapse' }}>
                    <thead>
                      <tr style={{ background: '#f5f5f5' }}>
                        <th style={{ padding: '3px 6px', border: '1px solid #e8e8e8', whiteSpace: 'nowrap' }}>单词</th>
                        <th style={{ padding: '3px 6px', border: '1px solid #e8e8e8' }}>释义</th>
                        <th style={{ padding: '3px 6px', border: '1px solid #e8e8e8' }}>使用对象</th>
                        <th style={{ padding: '3px 6px', border: '1px solid #e8e8e8' }}>使用场景</th>
                        <th style={{ padding: '3px 6px', border: '1px solid #e8e8e8' }}>正负态度</th>
                        <th style={{ padding: '3px 6px', border: '1px solid #e8e8e8' }}>排除理由</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries((point as any).word_analysis).map(([word, data]: [string, any]) => (
                        <tr key={word} style={{ background: word === point.correct_word ? '#e6f7ff' : 'white' }}>
                          <td style={{ padding: '3px 6px', border: '1px solid #e8e8e8', whiteSpace: 'nowrap' }}>
                            <Text strong={word === point.correct_word}>{word}</Text>
                          </td>
                          <td style={{ padding: '3px 6px', border: '1px solid #e8e8e8' }}>
                            <Text type="secondary" style={{ fontSize: 9 }}>{data.definition}</Text>
                          </td>
                          <td style={{ padding: '3px 6px', border: '1px solid #e8e8e8' }}>
                            {data.dimensions?.使用对象 || '-'}
                          </td>
                          <td style={{ padding: '3px 6px', border: '1px solid #e8e8e8' }}>
                            {data.dimensions?.使用场景 || '-'}
                          </td>
                          <td style={{ padding: '3px 6px', border: '1px solid #e8e8e8' }}>
                            {data.dimensions?.正负态度 || '-'}
                          </td>
                          <td style={{ padding: '3px 6px', border: '1px solid #e8e8e8', color: '#ff4d4f' }}>
                            {data.rejection_reason || '-'}
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
              <div style={{ marginTop: 8, padding: '8px 10px', background: '#f9f0ff', borderRadius: 6, border: '1px solid #d3adf7', maxHeight: 200, overflow: 'auto' }}>
                {(point as any).textbook_source && (
                  <div style={{ marginBottom: 4 }}>
                    <Text type="secondary" style={{ fontSize: 10 }}>课本出处：</Text>
                    <Text style={{ fontSize: 10 }}>{(point as any).textbook_source}</Text>
                  </div>
                )}
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 4 }}>
                  <div style={{ minWidth: 0 }}>
                    <Text type="secondary" style={{ fontSize: 10 }}>课本释义：</Text>
                    <Text style={{ fontSize: 10, wordBreak: 'break-word' }}>{(point as any).textbook_meaning}</Text>
                  </div>
                  <div style={{ minWidth: 0 }}>
                    <Text type="secondary" style={{ fontSize: 10 }}>语境释义：</Text>
                    <Text style={{ fontSize: 10, color: '#722ed1', wordBreak: 'break-word' }}>{(point as any).context_meaning}</Text>
                  </div>
                </div>
                {(point as any).similar_words && (point as any).similar_words.length > 0 && (
                  <div style={{ marginTop: 4 }}>
                    <Text type="secondary" style={{ fontSize: 10 }}>其他熟词僻义示例：</Text>
                    <div style={{ marginTop: 2, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                      {(point as any).similar_words.map((item: { word: string; textbook: string; rare: string }, i: number) => (
                        <Tag key={i} color="purple" style={{ fontSize: 9, marginBottom: 0, maxWidth: '100%', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', display: 'inline-block' }}>
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
              <div style={{ marginTop: 8, padding: '4px 8px', background: '#fffbe6', borderRadius: 4 }}>
                <Text type="secondary" style={{ fontSize: 10 }}>💡 {(point as any).tips}</Text>
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
            const tagColor = point ? getPointTagColor(point) : 'default'

            return (
              <Popover
                key={idx}
                content={point ? renderPointPopover(point, blankNum) : null}
                trigger="click"
                placement="bottom"
                arrow={false}
                overlayStyle={{ maxWidth: 420, maxHeight: '60vh' }}
                overlayInnerStyle={{ maxHeight: '60vh', overflow: 'auto' }}
                getPopupContainer={(triggerNode) => triggerNode.parentElement || document.body}
              >
                <Tag
                  ref={(el) => {
                    if (el) blankRefs.current.set(blankNum, el)
                  }}
                  color={tagColor}
                  style={{
                    cursor: 'pointer',
                    fontSize: 14,
                    padding: '2px 10px',
                    margin: '0 2px',
                    transition: 'all 0.3s ease',
                    boxShadow: isSelected ? '0 0 0 3px #1890ff, 0 2px 8px rgba(24,144,255,0.4)' : 'none',
                    transform: isSelected ? 'scale(1.2)' : 'scale(1)',
                    background: isSelected ? '#fffbe6' : undefined,
                    border: isSelected ? '2px solid #faad14' : undefined,
                  }}
                >
                  {blankNum}
                </Tag>
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
      const tagColor = point ? getPointTagColor(point) : 'default'

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
          <Tag
            ref={(el) => {
              if (el) blankRefs.current.set(bp.num, el)
            }}
            color={tagColor}
            style={{
              cursor: 'pointer',
              fontSize: 14,
              padding: '2px 10px',
              margin: '0 2px',
              boxShadow: isSelected ? '0 0 0 3px #1890ff, 0 2px 8px rgba(24,144,255,0.4)' : 'none',
              transform: isSelected ? 'scale(1.2)' : 'scale(1)',
              background: isSelected ? '#fffbe6' : undefined,
              border: isSelected ? '2px solid #faad14' : undefined,
            }}
          >
            {bp.num}
          </Tag>
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

  // 渲染单个考点卡片
  const renderPointCard = (point: ClozePoint, index: number) => {
    const blankNum = point.blank_number ?? (index + 1)
    const isSelected = selectedBlank === blankNum
    const tagColor = getPointTagColor(point)
    const displayName = getPointDisplayName(point)
    const showAnswer = showAnswerBlanks.has(blankNum)

    return (
      <div
        key={blankNum}
        ref={(el) => {
          if (el) pointRefs.current.set(blankNum, el)
        }}
        onClick={() => handlePointClick(blankNum)}
        className={`${styles.pointCard} ${isSelected ? styles.pointCardSelected : ''}`}
      >
        {/* 考点标题 */}
        <div className={styles.pointHeader}>
          <Space>
            <Tag color="blue" style={{ fontSize: 13, padding: '2px 10px', borderRadius: 12 }}>
              第 {blankNum} 空
            </Tag>
            <Tag color={tagColor} style={{ fontSize: 11, borderRadius: 8 }}>
              {displayName}
            </Tag>
          </Space>
          <Button
            size="small"
            type={showAnswer ? 'default' : 'primary'}
            icon={showAnswer ? <EyeInvisibleOutlined /> : <EyeOutlined />}
            onClick={(e) => toggleAnswerShow(blankNum, e)}
          >
            {showAnswer ? '隐藏答案' : '显示答案'}
          </Button>
        </div>

        {/* 选项 */}
        <div className={styles.optionsGrid}>
          {['A', 'B', 'C', 'D'].map(opt => {
            const optionValue = point.options?.[opt as keyof typeof point.options]
            const isCorrect = point.correct_answer === opt
            return (
              <Tag
                key={opt}
                color={showAnswer && isCorrect ? 'success' : 'default'}
                className={`${styles.optionTag} ${showAnswer && isCorrect ? styles.optionTagCorrect : ''}`}
              >
                {opt}. {optionValue}
                {showAnswer && isCorrect && point.correct_word && ` (${point.correct_word})`}
              </Tag>
            )
          })}
        </div>

        {/* 解析（显示答案时） */}
        {showAnswer && (
          <div className={styles.explanationBox}>
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
        {showAnswer && point.confusion_words && point.confusion_words.length > 0 && (
          <div className={styles.confusionList}>
            <Text type="secondary" style={{ fontSize: 11, marginBottom: 4, display: 'block' }}>易混淆词：</Text>
            {point.confusion_words.map((item: { word: string; meaning: string; reason: string }, idx: number) => (
              <div key={idx} className={styles.confusionItem}>
                <Text strong style={{ fontSize: 11 }}>{item.word}</Text>
                <Text type="secondary" style={{ fontSize: 11, marginLeft: 8 }}>
                  {item.meaning} — {item.reason}
                </Text>
              </div>
            ))}
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
          {(cloze as any).point_distribution_by_category && Object.keys((cloze as any).point_distribution_by_category).length > 0 && (
            <Space size={4}>
              {Object.entries((cloze as any).point_distribution_by_category).map(([category, count]) => (
                <Tag key={category} color={CAT_COLORS[category] || 'default'}>
                  {CATEGORY_NAMES[category] || category} ({count as number})
                </Tag>
              ))}
            </Space>
          )}
          {/* 考点分布 - v1 向后兼容 */}
          {!(cloze as any).point_distribution_by_category && Object.keys(cloze.point_distribution || {}).length > 0 && (
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
