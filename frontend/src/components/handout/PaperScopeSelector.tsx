import { useEffect, useMemo, useRef, useState } from 'react'
import { Button, Checkbox, Empty, Input, Select, Space, Spin, Tag, Typography } from 'antd'

import { listPapersByGrade } from '@/services/paperService'
import type { ModuleType } from '@/services/paperService'
import type { PaperSummary, WritingCategoryNode } from '@/types'

const { Text } = Typography

interface PaperScopeSelectorProps {
  grade: string
  moduleType: ModuleType
  selectedPaperIds: number[]
  onSelectedPaperIdsChange: (paperIds: number[]) => void
  onLoadingChange?: (loading: boolean) => void
  onAvailablePaperIdsChange?: (paperIds: number[]) => void
  fillAvailableHeight?: boolean
  excludePaperIds?: number[]  // 排除已生成的试卷 ID
  // 作文类别筛选项（由 WritingHandoutView 传入）
  groupCategories?: WritingCategoryNode[]
  majorCategories?: WritingCategoryNode[]
  categories?: WritingCategoryNode[]
  groupCategoryId?: number
  majorCategoryId?: number
  categoryId?: number
  onGroupCategoryIdChange?: (id: number | undefined) => void
  onMajorCategoryIdChange?: (id: number | undefined) => void
  onCategoryIdChange?: (id: number | undefined) => void
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

// 计算级联选项
function useCascadingOptions(
  groupCategories: WritingCategoryNode[] | undefined,
  majorCategories: WritingCategoryNode[] | undefined,
  categories: WritingCategoryNode[] | undefined,
  groupCategoryId: number | undefined,
  majorCategoryId: number | undefined
) {
  return useMemo(() => {
    const majorOptions = groupCategoryId
      ? (majorCategories || []).filter((m) => m.parent_id === groupCategoryId)
      : []
    const categoryOptions = majorCategoryId
      ? (categories || []).filter((c) => c.parent_id === majorCategoryId)
      : []
    return { majorOptions, categoryOptions }
  }, [groupCategories, majorCategories, categories, groupCategoryId, majorCategoryId])
}

export function PaperScopeSelector({
  grade,
  moduleType,
  selectedPaperIds,
  onSelectedPaperIdsChange,
  onLoadingChange,
  onAvailablePaperIdsChange,
  fillAvailableHeight = false,
  excludePaperIds = [],
  groupCategories,
  majorCategories,
  categories,
  groupCategoryId,
  majorCategoryId,
  categoryId,
  onGroupCategoryIdChange,
  onMajorCategoryIdChange,
  onCategoryIdChange,
}: PaperScopeSelectorProps) {
  const [papers, setPapers] = useState<PaperSummary[]>([])
  const [loading, setLoading] = useState(false)
  const [keyword, setKeyword] = useState('')
  const [filters, setFilters] = useState({
    year: undefined as number | undefined,
    region: undefined as string | undefined,
    school: undefined as string | undefined,
    examType: undefined as string | undefined,
    semester: undefined as string | undefined,
  })
  const initializedGradeRef = useRef<string | null>(null)

  const { majorOptions, categoryOptions } = useCascadingOptions(
    groupCategories, majorCategories, categories, groupCategoryId, majorCategoryId
  )

  useEffect(() => {
    let alive = true

    const loadPapers = async () => {
      try {
        setLoading(true)
        onLoadingChange?.(true)
        onAvailablePaperIdsChange?.([])
        const response = await listPapersByGrade(
          grade, 500, moduleType, categoryId, majorCategoryId, groupCategoryId
        )
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
  }, [grade, categoryId, majorCategoryId, groupCategoryId, onAvailablePaperIdsChange, onLoadingChange, moduleType])

  useEffect(() => {
    setKeyword('')
    setFilters({
      year: undefined,
      region: undefined,
      school: undefined,
      examType: undefined,
      semester: undefined,
    })
  }, [grade])

  // 级联清空：选中文体组时清空主类，选中主类时清空子类
  const handleGroupChange = (id: number | undefined) => {
    onGroupCategoryIdChange?.(id)
    onMajorCategoryIdChange?.(undefined)
    onCategoryIdChange?.(undefined)
  }

  const handleMajorChange = (id: number | undefined) => {
    onMajorCategoryIdChange?.(id)
    onCategoryIdChange?.(undefined)
  }

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

  const filterOptions = useMemo(() => {
    const years = [...new Set(displayPapers.map((p) => p.year).filter(Boolean))].sort(
      (a, b) => (b as number) - (a as number)
    )
    const regions = [...new Set(displayPapers.map((p) => p.region).filter(Boolean))].sort()
    const schools = [...new Set(displayPapers.map((p) => p.school).filter(Boolean))].sort()
    const examTypes = [...new Set(displayPapers.map((p) => p.exam_type).filter(Boolean))].sort()
    const semesters = [...new Set(displayPapers.map((p) => p.semester).filter(Boolean))].sort()
    return { years, regions, schools, examTypes, semesters }
  }, [displayPapers])

  const filteredPapers = useMemo(() => {
    let result = displayPapers

    if (filters.year !== undefined) {
      result = result.filter((p) => p.year === filters.year)
    }
    if (filters.region !== undefined) {
      result = result.filter((p) => p.region === filters.region)
    }
    if (filters.school !== undefined) {
      result = result.filter((p) => p.school === filters.school)
    }
    if (filters.examType !== undefined) {
      result = result.filter((p) => p.exam_type === filters.examType)
    }
    if (filters.semester !== undefined) {
      result = result.filter((p) => p.semester === filters.semester)
    }

    const normalizedKeyword = keyword.trim().toLowerCase()
    if (normalizedKeyword) {
      result = result.filter((paper) =>
        formatPaperLabel(paper).toLowerCase().includes(normalizedKeyword)
      )
    }

    return result
  }, [keyword, filters, displayPapers])

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
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {/* 作文类别三级筛选 */}
              <Select
                placeholder="文体组"
                allowClear
                size="small"
                style={{ width: 110 }}
                value={groupCategoryId}
                onChange={handleGroupChange}
                options={(groupCategories || []).map((g) => ({ value: g.id, label: g.name }))}
              />
              <Select
                placeholder="主类"
                allowClear
                size="small"
                style={{ width: 110 }}
                value={majorCategoryId}
                onChange={handleMajorChange}
                options={majorOptions.map((m) => ({ value: m.id, label: m.name }))}
                disabled={!groupCategoryId}
              />
              <Select
                placeholder="子类"
                allowClear
                size="small"
                style={{ width: 110 }}
                value={categoryId}
                onChange={onCategoryIdChange}
                options={categoryOptions.map((c) => ({ value: c.id, label: c.name }))}
                disabled={!majorCategoryId}
              />
              <Select
                placeholder="年份"
                allowClear
                size="small"
                style={{ width: 80 }}
                value={filters.year}
                onChange={(value) => setFilters((prev) => ({ ...prev, year: value }))}
                options={filterOptions.years.map((y) => ({ value: y, label: `${y}` }))}
              />
              <Select
                placeholder="区县"
                allowClear
                size="small"
                style={{ width: 90 }}
                value={filters.region}
                onChange={(value) => setFilters((prev) => ({ ...prev, region: value }))}
                options={filterOptions.regions.map((r) => ({ value: r, label: r }))}
              />
              <Select
                placeholder="考试类型"
                allowClear
                size="small"
                style={{ width: 90 }}
                value={filters.examType}
                onChange={(value) => setFilters((prev) => ({ ...prev, examType: value }))}
                options={filterOptions.examTypes.map((e) => ({ value: e, label: e }))}
              />
              <Select
                placeholder="学期"
                allowClear
                size="small"
                style={{ width: 75 }}
                value={filters.semester}
                onChange={(value) => setFilters((prev) => ({ ...prev, semester: value }))}
                options={filterOptions.semesters.map((s) => ({ value: s, label: `${s}学期` }))}
              />
              <Select
                placeholder="学校"
                allowClear
                showSearch
                size="small"
                style={{ width: 100 }}
                value={filters.school}
                onChange={(value) => setFilters((prev) => ({ ...prev, school: value }))}
                options={filterOptions.schools.map((s) => ({ value: s, label: s }))}
                filterOption={(input, option) =>
                  (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
                }
              />
            </div>

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
