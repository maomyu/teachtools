/**
 * 完形填空讲义视图容器
 *
 * [INPUT]: 依赖 antd, clozeService
 * [OUTPUT]: 对外提供 ClozeHandoutView 组件
 * [POS]: frontend/src/components/clozeHandout 的入口组件
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */
import { useState, useEffect } from 'react'
import { Alert, Button, Card, Empty, Grid, Radio, Space, Tag } from 'antd'
import { ArrowLeftOutlined, FileTextOutlined, ReloadOutlined } from '@ant-design/icons'
import { GradeSelector } from '@/components/handout/GradeSelector'
import { PaperScopeSelector } from '@/components/handout/PaperScopeSelector'
import { ClozeGradeHandout } from './ClozeGradeHandout'
import { getClozeFilters } from '@/services/clozeService'
import {
  getEffectiveHandoutPaperIds,
  getHandoutSelectionToken,
} from '@/utils/handoutSelection'

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

  // 加载年级列表
  useEffect(() => {
    loadGrades()
  }, [])

  useEffect(() => {
    setPaperLoading(Boolean(selectedGrade))
    if (!selectedGrade) {
      setAvailablePaperIds([])
    }
  }, [selectedGrade])

  const effectivePaperIds = getEffectiveHandoutPaperIds(selectedPaperIds, availablePaperIds)
  const currentSelectionToken = getHandoutSelectionToken(selectedPaperIds, availablePaperIds)
  const hasGenerated = generatedEdition !== null && generatedSelectionToken !== null
  const generationDirty = hasGenerated && (
    generatedEdition !== edition || generatedSelectionToken !== currentSelectionToken
  )
  const selectedCount = selectedPaperIds.length
  const totalCount = availablePaperIds.length || selectedPaperIds.length

  const resetSelectionState = () => {
    setSelectedGrade(null)
    setSelectedPaperIds([])
    setAvailablePaperIds([])
    setPaperLoading(false)
    setGeneratedPaperIds(undefined)
    setGeneratedEdition(null)
    setGeneratedSelectionToken(null)
  }

  const handleGenerate = () => {
    if (!selectedGrade || selectedPaperIds.length === 0 || paperLoading) return

    setGeneratedPaperIds(effectivePaperIds)
    setGeneratedEdition(edition)
    setGeneratedSelectionToken(currentSelectionToken)
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
              <PaperScopeSelector
                grade={selectedGrade}
                selectedPaperIds={selectedPaperIds}
                onSelectedPaperIdsChange={setSelectedPaperIds}
                onLoadingChange={setPaperLoading}
                onAvailablePaperIdsChange={setAvailablePaperIds}
                fillAvailableHeight={isSplitLayout}
              />
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
                        icon={hasGenerated ? <ReloadOutlined /> : <FileTextOutlined />}
                        onClick={handleGenerate}
                        disabled={paperLoading || selectedCount === 0}
                      >
                        {hasGenerated ? '重新生成讲义' : '生成讲义'}
                      </Button>
                    </Space>

                    <Space wrap>
                      <Tag color="blue">已选 {selectedCount} / {totalCount} 份试卷</Tag>
                      <Tag color={hasGenerated ? (generationDirty ? 'warning' : 'success') : 'default'}>
                        {hasGenerated ? (generationDirty ? '待重新生成' : '已生成') : '未生成'}
                      </Tag>
                      {hasGenerated && generatedEdition && (
                        <Tag color={generatedEdition === 'teacher' ? 'blue' : 'green'}>
                          当前结果：{generatedEdition === 'teacher' ? '教师版' : '学生版'}
                        </Tag>
                      )}
                    </Space>
                  </div>

                  {paperLoading ? (
                    <Alert showIcon type="info" message="正在同步试卷列表，请稍候后生成讲义。" />
                  ) : selectedCount === 0 ? (
                    <Alert showIcon type="warning" message="请至少保留一份试卷，否则无法生成完形讲义。" />
                  ) : !hasGenerated ? (
                    <Alert showIcon type="info" message={`已选 ${selectedCount} 份试卷，点击“生成讲义”后再加载完形讲义。`} />
                  ) : generationDirty ? (
                    <Alert
                      showIcon
                      type="warning"
                      message={`筛选条件或版本已变更，当前仍显示上次生成的${generatedEdition === 'teacher' ? '教师版' : '学生版'}讲义。点击“重新生成讲义”后更新。`}
                    />
                  ) : (
                    <Alert
                      showIcon
                      type="success"
                      message="完形讲义已根据当前试卷选择生成完成。调整筛选后，可点击“重新生成讲义”更新。"
                    />
                  )}
                </Space>
              </Card>
            </div>

            <div style={{ flex: '1 1 880px', minWidth: 0, overflow: isSplitLayout ? 'auto' : 'visible', minHeight: 0, height: isSplitLayout ? '100%' : 'auto' }}>
              {hasGenerated && selectedCount > 0 && generatedEdition ? (
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
                    description="左侧先筛选试卷，再点击“生成讲义”。右侧会在生成后展示完形讲义内容。"
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
