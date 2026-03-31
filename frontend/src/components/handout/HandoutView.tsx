/**
 * 讲义视图容器组件
 *
 * [INPUT]: 依赖 GradeSelector、GradeHandout、PaperScopeSelector、GeneratedPaperList
 * [OUTPUT]: 对外提供 HandoutView 组件
 * [POS]: frontend/src/components/handout 的讲义视图容器
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */
import { useState, useEffect, useCallback, useMemo } from 'react'
import { Alert, Badge, Button, Card, Empty, Grid, Radio, Typography, Space, Tabs, Tag } from 'antd'
import { ArrowLeftOutlined, CheckCircleOutlined, FileTextOutlined, ReloadOutlined } from '@ant-design/icons'

import { GradeSelector } from './GradeSelector'
import { GradeHandout } from './GradeHandout'
import { PaperScopeSelector } from './PaperScopeSelector'
import { GeneratedPaperList } from './GeneratedPaperList'
import { getGradeHandout, getPassageFilters } from '@/services/readingService'
import { getHandoutStatus, batchUpdateHandoutStatus } from '@/services/paperService'
import type { GradeHandoutResponse, HandoutStatusResponse } from '@/types'

const { Text } = Typography

type TabKey = 'not_generated' | 'generated'

export function HandoutView() {
  const screens = Grid.useBreakpoint()
  const isSplitLayout = Boolean(screens.lg)
  const [selectedGrade, setSelectedGrade] = useState<string | null>(null)
  const [edition, setEdition] = useState<'teacher' | 'student'>('teacher')
  const [selectedPaperIds, setSelectedPaperIds] = useState<number[]>([])
  const [availablePaperIds, setAvailablePaperIds] = useState<number[]>([])
  const [paperLoading, setPaperLoading] = useState(false)
  const [generatedPaperIds, setGeneratedPaperIds] = useState<number[] | undefined>(undefined)
  const [generatedSelectionToken, setGeneratedSelectionToken] = useState<string | null>(null)
  const [grades, setGrades] = useState<string[]>([])
  const [loadingGrades, setLoadingGrades] = useState(true)

  // === 双版本缓存 ===
  const [teacherHandoutData, setTeacherHandoutData] = useState<GradeHandoutResponse | null>(null)
  const [studentHandoutData, setStudentHandoutData] = useState<GradeHandoutResponse | null>(null)
  const [generating, setGenerating] = useState(false)

  // === 讲义生成状态 ===
  const [activeTab, setActiveTab] = useState<TabKey>('not_generated')
  const [handoutStatus, setHandoutStatus] = useState<HandoutStatusResponse | null>(null)
  const [loadingStatus, setLoadingStatus] = useState(false)

  // === 已生成 Tab 勾选 ===
  const [generatedCheckedIds, setGeneratedCheckedIds] = useState<number[]>([])

  // 已生成试卷的 ID 集合（提前计算，供合并与排除使用）
  const generatedPaperIdList = useMemo(
    () => handoutStatus?.generated.map((p) => p.id) || [],
    [handoutStatus]
  )

  // 合并两个 Tab 的选中试卷（过滤掉 selectedPaperIds 中已属于"已生成"的部分）
  const combinedPaperIds = useMemo(
    () => [...new Set([
      ...selectedPaperIds.filter((id) => !generatedPaperIdList.includes(id)),
      ...generatedCheckedIds,
    ])],
    [selectedPaperIds, generatedCheckedIds, generatedPaperIdList]
  )
  const combinedToken = combinedPaperIds.sort((a, b) => a - b).join(',')

  // 加载年级列表
  useEffect(() => { loadGrades() }, [])

  // 加载讲义生成状态
  useEffect(() => {
    if (selectedGrade) {
      loadHandoutStatus()
    } else {
      setHandoutStatus(null)
    }
  }, [selectedGrade])

  useEffect(() => {
    setPaperLoading(Boolean(selectedGrade))
    if (!selectedGrade) {
      setAvailablePaperIds([])
    }
  }, [selectedGrade])

  const hasGenerated = generatedSelectionToken !== null && (teacherHandoutData !== null || studentHandoutData !== null)
  const generationDirty = hasGenerated && generatedSelectionToken !== combinedToken
  const selectedCount = combinedPaperIds.length
  const totalCount = (availablePaperIds.length || selectedPaperIds.length) + generatedPaperIdList.length

  // 当前版本的缓存数据
  const currentHandoutData = edition === 'teacher' ? teacherHandoutData : studentHandoutData

  const resetSelectionState = useCallback(() => {
    setSelectedGrade(null)
    setSelectedPaperIds([])
    setAvailablePaperIds([])
    setPaperLoading(false)
    setGeneratedPaperIds(undefined)
    setGeneratedSelectionToken(null)
    setTeacherHandoutData(null)
    setStudentHandoutData(null)
    setActiveTab('not_generated')
    setHandoutStatus(null)
    setGeneratedCheckedIds([])
  }, [])

  const loadGrades = async () => {
    try {
      setLoadingGrades(true)
      const filters = await getPassageFilters()
      setGrades(filters.grades)
    } catch (error) {
      console.error('加载年级失败:', error)
    } finally {
      setLoadingGrades(false)
    }
  }

  const loadHandoutStatus = async () => {
    if (!selectedGrade) return
    try {
      setLoadingStatus(true)
      const status = await getHandoutStatus(selectedGrade, 'reading')
      setHandoutStatus(status)
    } catch (error) {
      console.error('加载讲义状态失败:', error)
      setHandoutStatus({ generated: [], not_generated: [] })
    } finally {
      setLoadingStatus(false)
    }
  }

  // === 核心生成逻辑 ===
  const doGenerate = useCallback(async (paperIds: number[]) => {
    if (!selectedGrade || paperIds.length === 0) return

    setGenerating(true)
    try {
      const response = await getGradeHandout(selectedGrade, 'both', paperIds)

      if (response.edition === 'both' && typeof response.content === 'object' && !Array.isArray(response.content)) {
        const { teacher, student } = response.content
        setTeacherHandoutData({ ...response, edition: 'teacher', content: teacher })
        setStudentHandoutData({ ...response, edition: 'student', content: student })
      }

      setGeneratedPaperIds(paperIds)
      setGeneratedSelectionToken([...paperIds].sort((a, b) => a - b).join(','))

      await batchUpdateHandoutStatus(paperIds, 'reading')
      await loadHandoutStatus()
    } catch (error) {
      console.error('生成讲义失败:', error)
    } finally {
      setGenerating(false)
    }
  }, [selectedGrade])

  // 底部按钮：合并两 Tab 选中
  const handleGenerate = () => {
    if (combinedPaperIds.length === 0) return
    doGenerate(combinedPaperIds)
  }

  return (
    <div style={{ padding: 24, height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* 版本切换器（始终显示） */}
      <div
        style={{
          marginBottom: 16,
          display: 'flex',
          justifyContent: selectedGrade ? 'space-between' : 'flex-start',
          alignItems: 'center',
        }}
      >
        {selectedGrade && (
          <Space>
            <Text strong style={{ fontSize: 16 }}>
              当前年级：{selectedGrade}
            </Text>
          </Space>
        )}

        <Space>
          <span style={{ fontWeight: 500 }}>版本：</span>
          <Radio.Group
            value={edition}
            onChange={(e) => setEdition(e.target.value)}
            buttonStyle="solid"
          >
            <Radio.Button value="teacher">教师版</Radio.Button>
            <Radio.Button value="student">学生版</Radio.Button>
          </Radio.Group>
        </Space>
      </div>

      {/* 内容区域 */}
      <div style={{ flex: 1, overflow: selectedGrade && isSplitLayout ? 'hidden' : 'auto', minHeight: 0 }}>
        {/* 年级选择 */}
        {!selectedGrade && (
          <GradeSelector
            grades={grades}
            loading={loadingGrades}
            title={edition === 'teacher' ? '阅读 CD篇（教师版）' : '阅读 CD篇（学生版）'}
            onSelect={setSelectedGrade}
          />
        )}

        {/* 年级讲义 */}
        {selectedGrade && (
          <div
            style={{
              display: 'flex',
              gap: 16,
              alignItems: 'flex-start',
              flexDirection: isSplitLayout ? 'row' : 'column',
              flexWrap: 'nowrap',
              height: isSplitLayout ? '100%' : 'auto',
              minHeight: 0,
            }}
          >
            <div
              style={{
                flex: isSplitLayout ? '0 0 360px' : '1 1 auto',
                width: isSplitLayout ? 360 : '100%',
                maxWidth: '100%',
                position: isSplitLayout ? 'sticky' : 'static',
                top: isSplitLayout ? 0 : undefined,
                alignSelf: isSplitLayout ? 'stretch' : 'auto',
                display: 'flex',
                flexDirection: 'column',
                gap: 16,
                height: isSplitLayout ? '100%' : 'auto',
                minHeight: 0,
              }}
            >
              {/* Tab 切换 */}
              <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
              <Tabs
                activeKey={activeTab}
                onChange={(key) => setActiveTab(key as TabKey)}
                className="handout-flex-tabs"
                style={{ marginBottom: 0 }}
                items={[
                  {
                    key: 'not_generated',
                    label: (
                      <Space size={4}>
                        <FileTextOutlined />
                        <span>未生成</span>
                        {handoutStatus && (
                          <Badge
                            count={handoutStatus.not_generated.length}
                            style={{ marginLeft: 4 }}
                            size="small"
                          />
                        )}
                      </Space>
                    ),
                    children: (
                      <PaperScopeSelector
                        grade={selectedGrade}
                        selectedPaperIds={selectedPaperIds}
                        onSelectedPaperIdsChange={setSelectedPaperIds}
                        onLoadingChange={setPaperLoading}
                        onAvailablePaperIdsChange={setAvailablePaperIds}
                        fillAvailableHeight={isSplitLayout}
                        excludePaperIds={generatedPaperIdList}
                      />
                    ),
                  },
                  {
                    key: 'generated',
                    label: (
                      <Space size={4}>
                        <CheckCircleOutlined />
                        <span>已生成</span>
                        {handoutStatus && (
                          <Badge
                            count={handoutStatus.generated.length}
                            style={{ marginLeft: 4 }}
                            size="small"
                            color="#52c41a"
                          />
                        )}
                      </Space>
                    ),
                    children: (
                      <GeneratedPaperList
                        papers={handoutStatus?.generated || []}
                        checkedIds={generatedCheckedIds}
                        onCheckedChange={setGeneratedCheckedIds}
                      />
                    ),
                  },
                ]}
              />
              </div>

              <Card style={{ flexShrink: 0 }}>
                <Space direction="vertical" size={12} style={{ width: '100%' }}>
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      gap: 12,
                      flexWrap: 'wrap',
                    }}
                  >
                    <Space wrap>
                      <Button icon={<ArrowLeftOutlined />} onClick={resetSelectionState}>
                        返回年级选择
                      </Button>
                      <Button
                        type="primary"
                        icon={generatedCheckedIds.length > 0 ? <ReloadOutlined /> : <FileTextOutlined />}
                        onClick={handleGenerate}
                        loading={generating}
                        disabled={paperLoading || combinedPaperIds.length === 0 || loadingStatus}
                      >
                        {generatedCheckedIds.length > 0 ? '重新生成讲义' : '生成讲义'}
                      </Button>
                    </Space>

                    <Space wrap>
                      <Tag color="blue">已选 {selectedCount} / {totalCount} 份试卷</Tag>
                      <Tag color={hasGenerated ? (generationDirty ? 'warning' : 'success') : 'default'}>
                        {hasGenerated ? (generationDirty ? '待重新生成' : '双版本已生成') : '未生成'}
                      </Tag>
                    </Space>
                  </div>

                  {paperLoading ? (
                    <Alert showIcon type="info" message="正在同步试卷列表，请稍候后生成讲义。" />
                  ) : combinedPaperIds.length === 0 ? (
                    <Alert showIcon type="warning" message="请在「未生成」Tab 选择试卷，或在「已生成」Tab 勾选后生成。" />
                  ) : !hasGenerated ? (
                    <Alert showIcon type="info" message={`已选 ${selectedCount} 份试卷。点击「生成讲义」将同时生成教师版和学生版。`} />
                  ) : generationDirty ? (
                    <Alert showIcon type="warning" message="试卷选择已变更。点击「重新生成讲义」更新教师版和学生版。" />
                  ) : (
                    <Alert showIcon type="success" message="教师版和学生版均已生成。切换版本即时显示，无需重新加载。" />
                  )}
                </Space>
              </Card>
            </div>

            <div style={{ flex: '1 1 880px', minWidth: 0, overflow: isSplitLayout ? 'auto' : 'visible', minHeight: 0, height: isSplitLayout ? '100%' : 'auto' }}>
              {hasGenerated && currentHandoutData ? (
                <GradeHandout
                  grade={selectedGrade}
                  edition={edition}
                  paperIds={generatedPaperIds}
                  onBack={resetSelectionState}
                  initialData={currentHandoutData}
                />
              ) : (
                <Card>
                  <Empty
                    image={Empty.PRESENTED_IMAGE_SIMPLE}
                    description="左侧先筛选试卷，再点击「生成讲义」。右侧会在生成后展示阅读讲义内容。"
                  />
                </Card>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
