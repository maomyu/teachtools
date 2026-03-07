/**
 * 阅读详情预览组件
 *
 * [INPUT]: 依赖 passageId、highlightWord、charPosition
 * [OUTPUT]: 对外提供 PassagePreview 组件
 * [POS]: frontend/src/components/vocabulary 的阅读预览
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Card,
  Typography,
  Spin,
  Space,
  Button,
  Tag,
} from 'antd'
import { EyeOutlined, LinkOutlined } from '@ant-design/icons'

import { getPassage } from '@/services/readingService'
import type { PassageDetail } from '@/types'

const { Text } = Typography

interface PassagePreviewProps {
  passageId: number
  highlightWord: string
  charPosition?: number
}

export function PassagePreview({
  passageId,
  highlightWord,
  charPosition,
}: PassagePreviewProps) {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [passage, setPassage] = useState<PassageDetail | null>(null)

  useEffect(() => {
    const loadPassage = async () => {
      setLoading(true)
      try {
        const data = await getPassage(passageId)
        setPassage(data)
      } catch (error) {
        console.error('加载文章失败:', error)
      } finally {
        setLoading(false)
      }
    }
    loadPassage()
  }, [passageId])

  // 渲染高亮内容
  const renderHighlightedContent = () => {
    if (!passage?.content) return null

    const content = passage.content
    const word = highlightWord.toLowerCase()
    const contentLower = content.toLowerCase()

    // 找到所有匹配位置
    const positions: number[] = []
    let start = 0
    while (true) {
      const pos = contentLower.indexOf(word, start)
      if (pos === -1) break
      positions.push(pos)
      start = pos + 1
    }

    if (positions.length === 0) {
      return <Text>{content}</Text>
    }

    // 构建高亮内容（只显示目标位置附近的文本）
    const targetPos = charPosition || positions[0]
    const contextStart = Math.max(0, targetPos - 150)
    const contextEnd = Math.min(content.length, targetPos + 200)
    const contextContent = content.slice(contextStart, contextEnd)

    // 重新计算在上下文中的位置
    const adjustedPositions = positions
      .filter(p => p >= contextStart && p < contextEnd)
      .map(p => p - contextStart)

    // 构建高亮文本
    const parts: React.ReactNode[] = []
    let lastEnd = 0

    adjustedPositions.forEach((pos, idx) => {
      const endPos = pos + word.length

      // 添加前面的普通文本
      if (pos > lastEnd) {
        parts.push(
          <span key={`text-${idx}`}>
            {contextContent.slice(lastEnd, pos)}
          </span>
        )
      }

      // 添加高亮文本（目标位置用不同样式）
      const isTarget = pos + contextStart === targetPos
      parts.push(
        <mark
          key={`highlight-${idx}`}
          style={{
            backgroundColor: isTarget ? '#ffeb3b' : '#fff3cd',
            padding: '0 2px',
            borderRadius: '2px',
            fontWeight: isTarget ? 'bold' : undefined,
          }}
        >
          {contextContent.slice(pos, endPos)}
        </mark>
      )

      lastEnd = endPos
    })

    // 添加最后的普通文本
    if (lastEnd < contextContent.length) {
      parts.push(
        <span key="text-end">
          {contextContent.slice(lastEnd)}
        </span>
      )
    }

    return (
      <>
        {contextStart > 0 && <Text>...</Text>}
        <Text>{parts}</Text>
        {contextEnd < content.length && <Text>...</Text>}
      </>
    )
  }

  if (loading) {
    return (
      <Card size="small" style={{ marginTop: 16, textAlign: 'center', padding: 24 }}>
        <Spin />
      </Card>
    )
  }

  if (!passage) {
    return null
  }

  const source = passage.source

  return (
    <Card
      size="small"
      style={{
        marginTop: 16,
        animation: 'slideIn 0.3s ease-out',
      }}
      title={
        <Space>
          <span>阅读详情预览</span>
          <Tag color="blue">{passage.passage_type}篇</Tag>
        </Space>
      }
      extra={
        <Button
          type="link"
          size="small"
          icon={<LinkOutlined />}
          onClick={() => navigate(`/reading/${passageId}`)}
        >
          打开完整文章
        </Button>
      }
    >
      {/* 出处信息 */}
      <Space size="small" style={{ marginBottom: 12 }}>
        {source?.year && <Tag>{source.year}</Tag>}
        {source?.region && <Tag color="blue">{source.region}</Tag>}
        {source?.grade && <Tag color="green">{source.grade}</Tag>}
        {source?.exam_type && <Tag color="orange">{source.exam_type}</Tag>}
        {passage.primary_topic && <Tag color="purple">{passage.primary_topic}</Tag>}
      </Space>

      {/* 高亮内容 */}
      <div
        style={{
          padding: '12px 16px',
          background: '#fafafa',
          borderRadius: 4,
          lineHeight: 1.8,
          fontSize: 14,
        }}
      >
        {renderHighlightedContent()}
      </div>

      {/* 操作按钮 */}
      <Space style={{ marginTop: 12 }}>
        <Button
          type="primary"
          icon={<EyeOutlined />}
          onClick={() => navigate(`/reading/${passageId}`)}
        >
          查看完整文章
        </Button>
      </Space>
    </Card>
  )
}
