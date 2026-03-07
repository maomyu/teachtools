/**
 * 词汇详情面板
 *
 * [INPUT]: 依赖 Vocabulary 类型、 searchVocabulary API
 * [OUTPUT]: 对外提供 VocabularyDetailPanel 组件
 * [POS]: frontend/src/components/vocabulary 的词汇详情面板
 * [PROTOCOL]: 变更时更新此头部,然后检查 CLAUDE.md
 */
import { useState, useEffect } from 'react'
import {
  Card,
  Tag,
  Typography,
  Spin,
  Empty,
  Space,
  Button,
} from 'antd'
import { BookOutlined } from '@ant-design/icons'

import { searchVocabulary } from '@/services/vocabularyService'
import type { Vocabulary, VocabularyOccurrence } from '@/types'
import { OccurrenceCard } from './OccurrenceCard'

const { Text, Paragraph } = Typography

/** 筛选条件类型 */
export interface VocabularyFilters {
  grade?: string
  topic?: string
  year?: number
  region?: string
  exam_type?: string
  semester?: string
}

interface VocabularyDetailPanelProps {
  word: Vocabulary
  filters?: VocabularyFilters
  onViewFullPassage: (passageId: number, charPosition?: number) => void
}

const PAGE_SIZE = 10

export function VocabularyDetailPanel({
  word,
  filters,
  onViewFullPassage,
}: VocabularyDetailPanelProps) {
  const [loading, setLoading] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [occurrences, setOccurrences] = useState<VocabularyOccurrence[]>([])
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [hasMore, setHasMore] = useState(false)

  // 词汇变化时重置并加载
  useEffect(() => {
    let cancelled = false

    const loadData = async () => {
      setLoading(true)
      setOccurrences([])
      try {
        const data = await searchVocabulary(word.word, 1, PAGE_SIZE, filters)
        if (!cancelled) {
          setOccurrences(data.occurrences || [])
          setTotal(data.total)
          setHasMore(data.has_more)
          setPage(data.page)
        }
      } catch (error) {
        console.error('加载例句失败:', error)
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    loadData()

    return () => {
      cancelled = true
    }
  }, [word.word, filters?.grade, filters?.topic, filters?.year, filters?.region])

  const loadMore = async () => {
    if (loadingMore || !hasMore) return

    setLoadingMore(true)
    try {
      const nextPage = page + 1
      const data = await searchVocabulary(word.word, nextPage, PAGE_SIZE, filters)
      setOccurrences(prev => [...prev, ...(data.occurrences || [])])
      setHasMore(data.has_more)
      setPage(nextPage)
    } catch (error) {
      console.error('加载更多失败:', error)
    } finally {
      setLoadingMore(false)
    }
  }

  const handleLoadMore = () => {
    loadMore()
  }

  // 点击例句卡片 -> 直接打开抽屉
  const handleOccurrenceClick = (occ: VocabularyOccurrence) => {
    onViewFullPassage(occ.passage_id, occ.char_position)
  }

  return (
    <div style={{ padding: '0 16px' }}>
      {/* 词汇基本信息卡片 */}
      <Card size="small" style={{ marginBottom: 16 }}>
        <Space direction="vertical" style={{ width: '100%' }}>
          <Space>
            <BookOutlined style={{ color: '#1890ff' }} />
            <Text strong style={{ fontSize: 20 }}>{word.word}</Text>
            <Tag color="blue" style={{ marginLeft: 8 }}>
              词频: {total} 次
            </Tag>
          </Space>
          <div>
            <Text type="secondary">释义</Text>
            <Paragraph style={{ margin: '8px 0', fontSize: 15 }}>
              {word.definition || '暂无释义'}
            </Paragraph>
          </div>
        </Space>
      </Card>

      {/* 例句列表标题 */}
      <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <Text strong>出现位置</Text>
          <Tag color="green" style={{ marginLeft: 8 }}>{total} 处</Tag>
        </div>
        {hasMore && (
          <Text type="secondary" style={{ fontSize: 12 }}>
            已加载 {occurrences.length} / {total} 条
          </Text>
        )}
      </div>

      {/* 例句列表 */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: 40 }}>
          <Spin />
        </div>
      ) : occurrences.length === 0 ? (
        <Empty description="暂无例句" />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
          {occurrences.map((occ) => (
            <OccurrenceCard
              key={`${occ.passage_id}-${occ.char_position}`}
              occurrence={occ}
              onClick={() => handleOccurrenceClick(occ)}
            />
          ))}
        </div>
      )}

      {/* 加载更多按钮 */}
      {hasMore && (
        <div style={{ textAlign: 'center', padding: 16 }}>
          <Button
            type="primary"
            loading={loadingMore}
            onClick={handleLoadMore}
          >
            {loadingMore ? '加载中...' : '加载更多'}
          </Button>
        </div>
      )}
    </div>
  )
}
