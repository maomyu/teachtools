import { useEffect, useMemo, useRef, useState } from 'react'
import { Button, Checkbox, Empty, Input, Space, Spin, Tag, Typography } from 'antd'

import { listPapersByGrade } from '@/services/paperService'
import type { PaperSummary } from '@/types'

const { Text } = Typography

interface PaperScopeSelectorProps {
  grade: string
  selectedPaperIds: number[]
  onSelectedPaperIdsChange: (paperIds: number[]) => void
  onLoadingChange?: (loading: boolean) => void
  onAvailablePaperIdsChange?: (paperIds: number[]) => void
  fillAvailableHeight?: boolean
  excludePaperIds?: number[]  // 排除已生成的试卷 ID
}

function formatPaperLabel(paper: PaperSummary): string {
  const meta = [
    paper.year,
    paper.region,
    paper.grade,
    paper.semester ? `${paper.semester}` : null,
    paper.exam_type,
    paper.version,
  ].filter(Boolean).join(' · ')

  return `${meta} · ${paper.filename}`
}

export function PaperScopeSelector({
  grade,
  selectedPaperIds,
  onSelectedPaperIdsChange,
  onLoadingChange,
  onAvailablePaperIdsChange,
  fillAvailableHeight = false,
  excludePaperIds = [],
}: PaperScopeSelectorProps) {
  const [papers, setPapers] = useState<PaperSummary[]>([])
  const [loading, setLoading] = useState(false)
  const [keyword, setKeyword] = useState('')
  const initializedGradeRef = useRef<string | null>(null)

  useEffect(() => {
    let alive = true

    const loadPapers = async () => {
      try {
        setLoading(true)
        onLoadingChange?.(true)
        onAvailablePaperIdsChange?.([])
        const response = await listPapersByGrade(grade)
        if (!alive) return
        setPapers(response.items || [])
      } catch (error) {
        console.error('加载试卷列表失败:', error)
        if (!alive) return
        setPapers([])
        onAvailablePaperIdsChange?.([])
      } finally {
        if (alive) {
          setLoading(false)
          onLoadingChange?.(false)
        }
      }
    }

    loadPapers()

    return () => {
      alive = false
    }
  }, [grade, onAvailablePaperIdsChange, onLoadingChange])

  useEffect(() => {
    setKeyword('')
  }, [grade])

  useEffect(() => {
    onAvailablePaperIdsChange?.(papers.map((paper) => paper.id))
  }, [onAvailablePaperIdsChange, papers])

  useEffect(() => {
    const allPaperIds = papers.map((paper) => paper.id)
    if (loading || allPaperIds.length === 0) return

    if (initializedGradeRef.current !== grade) {
      initializedGradeRef.current = grade
      onSelectedPaperIdsChange([])
      return
    }

    const availableIdSet = new Set(allPaperIds)
    const validSelectedIds = selectedPaperIds.filter((paperId) => availableIdSet.has(paperId))

    if (validSelectedIds.length !== selectedPaperIds.length) {
      onSelectedPaperIdsChange(validSelectedIds)
    }
  }, [grade, loading, onSelectedPaperIdsChange, papers, selectedPaperIds])

  const selectedCount = selectedPaperIds.length

  // 过滤掉已生成的试卷
  const displayPapers = useMemo(() => {
    if (excludePaperIds.length === 0) return papers
    const excludeSet = new Set(excludePaperIds)
    return papers.filter((paper) => !excludeSet.has(paper.id))
  }, [papers, excludePaperIds])

  const allPaperIds = useMemo(() => displayPapers.map((paper) => paper.id), [displayPapers])

  const filteredPapers = useMemo(() => {
    const normalizedKeyword = keyword.trim().toLowerCase()
    if (!normalizedKeyword) return displayPapers

    return displayPapers.filter((paper) =>
      formatPaperLabel(paper).toLowerCase().includes(normalizedKeyword)
    )
  }, [keyword, displayPapers])

  return (
    <div style={{
      marginBottom: fillAvailableHeight ? 0 : 16,
      padding: 16,
      background: '#fafafa',
      border: '1px solid #f0f0f0',
      borderRadius: 8,
      display: 'flex',
      flexDirection: 'column',
      minHeight: 0,
      height: fillAvailableHeight ? '100%' : undefined,
      flex: fillAvailableHeight ? 1 : undefined,
    }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, width: '100%', minHeight: 0, flex: 1 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
          <Space wrap>
            <Text strong>试卷列表：</Text>
            <Button
              size="small"
              onClick={() => onSelectedPaperIdsChange(allPaperIds)}
              disabled={loading || allPaperIds.length === 0}
            >
              全选当前年级
            </Button>
            <Button
              size="small"
              onClick={() => onSelectedPaperIdsChange([])}
              disabled={loading || selectedCount === 0}
            >
              清空选择
            </Button>
          </Space>

          <Space wrap>
            <Tag color="processing">当前年级：{grade}</Tag>
            <Tag color="blue">已选 {selectedCount} / {displayPapers.length} 份试卷</Tag>
          </Space>
        </div>

        {loading ? (
          <div style={{ padding: '8px 0' }}>
            <Spin size="small" /> <Text type="secondary">正在加载试卷列表...</Text>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12, width: '100%', minHeight: 0, flex: 1 }}>
            <Input
              allowClear
              value={keyword}
              onChange={(event) => setKeyword(event.target.value)}
              placeholder="搜索试卷：年份 / 区县 / 期中期末 / 文件名"
            />

            {filteredPapers.length === 0 ? (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description="没有匹配的试卷"
              />
            ) : (
              <div
                style={{
                  maxHeight: fillAvailableHeight ? 'none' : 280,
                  overflowY: 'auto',
                  padding: 12,
                  border: '1px solid #f0f0f0',
                  borderRadius: 8,
                  background: '#fff',
                  minHeight: 0,
                  flex: fillAvailableHeight ? 1 : undefined,
                }}
              >
                <Checkbox.Group
                  value={selectedPaperIds}
                  onChange={(values) =>
                    onSelectedPaperIdsChange(values.map((value) => Number(value)))
                  }
                  style={{ width: '100%' }}
                >
                  <Space direction="vertical" size={8} style={{ width: '100%' }}>
                    {filteredPapers.map((paper) => (
                      <div
                        key={paper.id}
                        style={{
                          padding: '2px 4px',
                          borderRadius: 6,
                          border: '1px solid #f5f5f5',
                        }}
                      >
                        <Checkbox value={paper.id} style={{ width: '100%' }}>
                          <div style={{ minWidth: 0 }}>
                            <div style={{ fontWeight: 500, color: '#262626', wordBreak: 'break-word' }}>
                              {paper.filename}
                            </div>
                            <Text type="secondary" style={{ fontSize: 12 }}>
                              {[
                                paper.year,
                                paper.region,
                                paper.grade,
                                paper.semester ? `${paper.semester}学期` : null,
                                paper.exam_type,
                                paper.version,
                              ].filter(Boolean).join(' · ')}
                            </Text>
                          </div>
                        </Checkbox>
                      </div>
                    ))}
                  </Space>
                </Checkbox.Group>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
