/**
 * 完形填空讲义视图容器
 *
 * [INPUT]: 依赖 antd, clozeService, paperService, PaperScopeSelector, GeneratedPaperList
 * [OUTPUT]: 对外提供 ClozeHandoutView 组件
 * [POS]: frontend/src/components/clozeHandout 的入口组件
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */
import { useState, useEffect, useCallback, useMemo } from 'react'
import { Alert, Badge, Button, Card, Empty, Grid, Radio, Space, Tabs, Tag } from 'antd'
import { ArrowLeftOutlined, CheckCircleOutlined, FileTextOutlined, ReloadOutlined } from '@ant-design/icons'
import { GradeSelector } from '@/components/handout/GradeSelector'
import { PaperScopeSelector } from '@/components/handout/PaperScopeSelector'
import { GeneratedPaperList } from '@/components/handout/GeneratedPaperList'
import { ClozeGradeHandout } from './ClozeGradeHandout'
import { getClozeFilters } from '@/services/clozeService'
import { getHandoutStatus, batchUpdateHandoutStatus } from '@/services/paperService'
import type { HandoutStatusResponse } from '@/types'

type TabKey = 'not_generated' | 'generated'

export function ClozeHandoutView() {
  const screens = Grid.useBreakpoint()
  const isSplitLayout = Boolean(screens.lg)
  const [selectedGrade, setSelectedGrade] = useState<string | null>(null)
  const [edition, setEdition] = useState<'teacher' | 'student'>('teacher')
  const [selectedPaperIds, setSelectedPaperIds] = useState<number[]>([])
  const [availablePaperIds, setAvailablePaperIds] = useState<number[]>([])
  const [paperLoading, setPaperLoading] = useState(false)
  const [generatedPaperIds, setGeneratedPaperIds] = useState<number[] | undefined>(undefined)
  const [generatedEdition, setGeneratedEdition] = useState<'teacher' | 'student' | null>(null)
  const [generatedSelectionToken, setGeneratedSelectionToken] = useState<string | null>(null)
  const [grades, setGrades] = useState<string[]>([])
  const [loadingGrades, setLoadingGrades] = useState(true)

  // === 生成记录追踪 ===
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

  const hasGenerated = generatedEdition !== null && generatedSelectionToken !== null
  const generationDirty = hasGenerated && generatedSelectionToken !== combinedToken
  const selectedCount = combinedPaperIds.length
  const totalCount = (availablePaperIds.length || selectedPaperIds.length) + generatedPaperIdList.length

  const resetSelectionState = useCallback(() => {
    setSelectedGrade(null)
    setSelectedPaperIds([])
    setAvailablePaperIds([])
    setPaperLoading(false)
    setGeneratedPaperIds(undefined)
    setGeneratedEdition(null)
    setGeneratedSelectionToken(null)
    setActiveTab('not_generated')
    setHandoutStatus(null)
    setGeneratedCheckedIds([])
  }, [])

  // === 核心生成逻辑 ===
  const doGenerate = useCallback(async (paperIds: number[]) => {
    if (!selectedGrade || paperIds.length === 0) return

    setGeneratedPaperIds(paperIds)
    setGeneratedEdition(edition)
    setGeneratedSelectionToken([...paperIds].sort((a, b) => a - b).join(','))

    await batchUpdateHandoutStatus(paperIds, 'cloze')
    await loadHandoutStatus()
  }, [selectedGrade, edition])

  // 底部按钮：合并两 Tab 选中
  const handleGenerate = () => {
    if (combinedPaperIds.length === 0) return
    doGenerate(combinedPaperIds)
  }

  const loadGrades = async () => {
    try {
      setLoadingGrades(true)
      const filters = await getClozeFilters()
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
      const status = await getHandoutStatus(selectedGrade, 'cloze')
      setHandoutStatus(status)
    } catch (error) {
      console.error('加载讲义状态失败:', error)
      setHandoutStatus({ generated: [], not_generated: [] })
    } finally {
      setLoadingStatus(false)
    }
  }

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* 顶部工具栏：版本切换（右上角） */}
      <div style={{
        display: 'flex',
        justifyContent: 'flex-end',
        alignItems: 'center',
        marginBottom: 16
      }}>
        <Space>
          <span style={{ fontWeight: 500 }}>版本：</span>
          <Radio.Group
            value={edition}
            onChange={(e) => setEdition(e.target.value)}
            optionType="button"
            buttonStyle="solid"
          >
            <Radio.Button value="teacher">教师版</Radio.Button>
            <Radio.Button value="student">学生版</Radio.Button>
          </Radio.Group>
        </Space>
      </div>

      {/* 年级选择或讲义内容 */}
      <div style={{ flex: 1, overflow: selectedGrade && isSplitLayout ? 'hidden' : 'auto', minHeight: 0 }}>
        {!selectedGrade ? (
          <GradeSelector
            grades={grades}
            loading={loadingGrades}
            title={edition === 'teacher' ? '完形填空（教师版）' : '完形填空（学生版）'}
            onSelect={setSelectedGrade}
          />
        ) : (
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
                        disabled={paperLoading || combinedPaperIds.length === 0 || loadingStatus}
                      >
                        {generatedCheckedIds.length > 0 ? '重新生成讲义' : '生成讲义'}
                      </Button>
                    </Space>

                    <Space wrap>
                      <Tag color="blue">已选 {selectedCount} / {totalCount} 份试卷</Tag>
                      <Tag color={hasGenerated ? (generationDirty ? 'warning' : 'success') : 'default'}>
                        {hasGenerated ? (generationDirty ? '待重新生成' : '已生成') : '未生成'}
                      </Tag>
                    </Space>
                  </div>

                  {paperLoading ? (
                    <Alert showIcon type="info" message="正在同步试卷列表，请稍候后生成讲义。" />
                  ) : combinedPaperIds.length === 0 ? (
                    <Alert showIcon type="warning" message="请在「未生成」Tab 选择试卷，或在「已生成」Tab 勾选后生成。" />
                  ) : !hasGenerated ? (
                    <Alert showIcon type="info" message={`已选 ${selectedCount} 份试卷，点击「生成讲义」后将自动记录到「已生成」列表。`} />
                  ) : generationDirty ? (
                    <Alert showIcon type="warning" message="试卷选择已变更，点击「重新生成讲义」更新。" />
                  ) : (
                    <Alert showIcon type="success" message="完形讲义已生成完成。调整筛选后，可点击「重新生成讲义」更新。" />
                  )}
                </Space>
              </Card>
            </div>

            <div style={{ flex: '1 1 880px', minWidth: 0, overflow: isSplitLayout ? 'auto' : 'visible', minHeight: 0, height: isSplitLayout ? '100%' : 'auto' }}>
              {hasGenerated && generatedEdition ? (
                <ClozeGradeHandout
                  grade={selectedGrade}
                  edition={generatedEdition}
                  paperIds={generatedPaperIds}
                  onBack={resetSelectionState}
                />
              ) : (
                <Card>
                  <Empty
                    image={Empty.PRESENTED_IMAGE_SIMPLE}
                    description="左侧先筛选试卷，再点击「生成讲义」。右侧会在生成后展示完形讲义内容。"
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
