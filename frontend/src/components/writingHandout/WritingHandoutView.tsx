/**
 * 作文讲义视图容器组件
 *
 * [INPUT]: 依赖 antd、GradeWritingHandout
 * [OUTPUT]: 对外提供 WritingHandoutView 组件
 * [POS]: frontend/src/components/writingHandout 的讲义视图容器
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */
import { useState, useEffect } from 'react'
import { Alert, Button, Row, Col, Card, Grid, Radio, Typography, Space, Tag, Spin, Empty } from 'antd'
import { ArrowLeftOutlined, BookOutlined, FileTextOutlined, ReloadOutlined } from '@ant-design/icons'

import { GradeWritingHandout } from './GradeWritingHandout'
import { PaperScopeSelector } from '@/components/handout/PaperScopeSelector'
import { getWritingFilters } from '@/services/writingService'
import {
  getEffectiveHandoutPaperIds,
  getHandoutSelectionToken,
} from '@/utils/handoutSelection'

const { Title, Text } = Typography

// 年级颜色映射
const GRADE_COLORS: Record<string, string> = {
  '初一': '#1890ff',
  '初二': '#52c41a',
  '初三': '#722ed1',
}

// ============================================================================
//  主组件
// ============================================================================

export function WritingHandoutView() {
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
  const [availableGrades, setAvailableGrades] = useState<string[]>([])
  const [loading, setLoading] = useState(true)

  // 加载可用的年级
  useEffect(() => {
    loadAvailableGrades()
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

  const loadAvailableGrades = async () => {
    try {
      setLoading(true)
      const filters = await getWritingFilters()
      setAvailableGrades(filters.grades || [])
    } catch (error) {
      console.error('加载年级列表失败:', error)
    } finally {
      setLoading(false)
    }
  }

  // 如果已选择年级，显示讲义内容
  if (selectedGrade) {
    return (
      <div style={{ padding: 24, height: isSplitLayout ? '100%' : 'auto', minHeight: 0 }}>
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
                  <Alert showIcon type="warning" message="请至少保留一份试卷，否则无法生成作文讲义。" />
                ) : !hasGenerated ? (
                  <Alert showIcon type="info" message={`已选 ${selectedCount} 份试卷，点击“生成讲义”后再加载作文讲义。`} />
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
                    message="作文讲义已根据当前试卷选择生成完成。调整筛选后，可点击“重新生成讲义”更新。"
                  />
                )}
              </Space>
            </Card>
          </div>

          <div style={{ flex: '1 1 880px', minWidth: 0, overflow: isSplitLayout ? 'auto' : 'visible', minHeight: 0, height: isSplitLayout ? '100%' : 'auto' }}>
            {hasGenerated && selectedCount > 0 && generatedEdition ? (
              <GradeWritingHandout
                grade={selectedGrade}
                edition={generatedEdition}
                paperIds={generatedPaperIds}
                onBack={resetSelectionState}
              />
            ) : (
              <Card>
                <Empty
                  image={Empty.PRESENTED_IMAGE_SIMPLE}
                  description="左侧先筛选试卷，再点击“生成讲义”。右侧会在生成后展示作文讲义内容。"
                />
              </Card>
            )}
          </div>
        </div>
      </div>
    )
  }

  // 加载中
  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 48 }}>
        <Spin size="large" tip="加载年级数据..." />
      </div>
    )
  }

  // 没有数据
  if (availableGrades.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: 48 }}>
        <Empty description="暂无作文数据，请先导入作文题目" />
      </div>
    )
  }

  // 年级选择界面
  return (
    <div style={{ padding: 24 }}>
      {/* 版本切换器 */}
      <div style={{ marginBottom: 24, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Title level={3} style={{ margin: 0 }}>
          <BookOutlined style={{ marginRight: 8 }} />
          作文讲义
        </Title>
        <Radio.Group
          value={edition}
          onChange={(e) => setEdition(e.target.value)}
          buttonStyle="solid"
        >
          <Radio.Button value="teacher">教师版</Radio.Button>
          <Radio.Button value="student">学生版</Radio.Button>
        </Radio.Group>
      </div>

      {/* 说明 */}
      <Card style={{ marginBottom: 24 }}>
        <Space direction="vertical">
          <Text>作文讲义按<strong>话题分类</strong>，采用<strong>四段式结构</strong>：</Text>
          <ul style={{ margin: 0, paddingLeft: 20 }}>
            <li><Text>话题目录 - 统计各话题的题目数量和考查年份</Text></li>
            <li><Text>写作框架 - 标准结构模板（开头句、背景句、中心句、主体段、结尾句）</Text></li>
            <li><Text>高频表达 - 开头句型、结尾句型、过渡词汇、高级词汇</Text></li>
            <li><Text>范文展示 - 真题范文 + 重点句标注（教师版含解析）</Text></li>
          </ul>
        </Space>
      </Card>

      {/* 年级选择 - 只显示有数据的年级 */}
      <Title level={4}>选择年级</Title>
      <Row gutter={[16, 16]}>
        {availableGrades.map((grade) => (
          <Col xs={24} sm={12} md={8} key={grade}>
            <Card
              hoverable
              onClick={() => setSelectedGrade(grade)}
              style={{
                textAlign: 'center',
                cursor: 'pointer',
                borderLeft: `4px solid ${GRADE_COLORS[grade] || '#999'}`,
              }}
            >
              <Title level={2} style={{ margin: 0, color: GRADE_COLORS[grade] || '#999' }}>
                {grade}
              </Title>
              <Text type="secondary">作文讲义</Text>
            </Card>
          </Col>
        ))}
      </Row>

      {/* 当前版本提示 */}
      <div style={{ marginTop: 24, textAlign: 'center' }}>
        <Tag color={edition === 'teacher' ? 'blue' : 'green'}>
          当前：{edition === 'teacher' ? '教师版（含重点句解析）' : '学生版'}
        </Tag>
      </div>
    </div>
  )
}
