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
  Tag,
  Typography,
  Spin,
  Empty,
  Button,
} from 'antd'

import { searchVocabulary } from '@/services/vocabularyService'
import type { Vocabulary, VocabularyOccurrence } from '@/types'
import { OccurrenceCard } from './OccurrenceCard'

const { Text } = Typography

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
  onViewFullPassage: (passageId: number, charPosition?: number, sourceType?: 'reading' | 'cloze') => void
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
    onViewFullPassage(occ.passage_id, occ.char_position, occ.source_type)
  }

  return (
    <div style={{
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      padding: '12px 8px',
    }}>
      {/* 词汇基本信息 - 紧凑布局 */}
      <div style={{ marginBottom: 8, paddingBottom: 8, borderBottom: '1px solid #f0f0f0', flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
          <Text strong style={{ fontSize: 16 }}>{word.word}</Text>
          <Tag color="blue" style={{ fontSize: 11 }}>词频: {total}</Tag>
        </div>
        <Text type="secondary" style={{ fontSize: 12 }}>{word.definition || '暂无释义'}</Text>
      </div>

      {/* 例句列表标题 */}
      <div style={{ marginBottom: 6, marginTop: 4, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0 }}>
        <Text strong style={{ fontSize: 13 }}>出现位置 <Tag color="green" style={{ fontSize: 10, marginLeft: 4 }}>{total} 处</Tag></Text>
        {hasMore && (
          <Text type="secondary" style={{ fontSize: 10 }}>
            {occurrences.length}/{total}
          </Text>
        )}
      </div>

      {/* 例句列表 - 填充剩余空间 */}
      <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
        {loading ? (
          <div style={{ textAlign: 'center', padding: 24 }}>
            <Spin size="small" />
          </div>
        ) : occurrences.length === 0 ? (
          <Empty description="暂无例句" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {occurrences.map((occ) => (
              <OccurrenceCard
                key={`${occ.passage_id}-${occ.char_position}`}
                occurrence={occ}
                onClick={() => handleOccurrenceClick(occ)}
              />
            ))}
          </div>
        )}
      </div>

      {/* 加载更多按钮 - 固定在底部 */}
      {hasMore && (
        <div style={{ textAlign: 'center', marginTop: 12, flexShrink: 0 }}>
          <Button
            type="link"
            size="small"
            loading={loadingMore}
            onClick={handleLoadMore}
          >
            {loadingMore ? '加载中...' : '加载更多...'}
          </Button>
        </div>
      )}
    </div>
  )
}
