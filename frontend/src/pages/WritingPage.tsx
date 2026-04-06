/**
 * 作文列表页（模板驱动版）
 *
 * [INPUT]: 依赖 antd 组件、@/services/writingService、@/types
 * [OUTPUT]: 对外提供 WritingPage 组件
 * [POS]: frontend/src/pages 的作文列表页面
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Alert,
  Badge,
  Card,
  Col,
  Descriptions,
  Empty,
  Grid,
  Input,
  Radio,
  Row,
  Select,
  Space,
  Spin,
  Table,
  Tabs,
  Tag,
  Typography,
  message,
} from 'antd'
import {
  BookOutlined,
  FileTextOutlined,
  ReadOutlined,
  UnorderedListOutlined,
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'

import {
  getWritingFilters,
  getWritingTemplatePaperDetail,
  getWritingTemplatePapers,
  getWritingTemplates,
} from '@/services/writingService'
import type {
  WritingFilter,
  WritingFiltersResponse,
  WritingSample,
  WritingTaskDetail,
  WritingTemplateListItem,
  WritingTemplatePaperDetailResponse,
  WritingTemplatePaperItem,
} from '@/types'
import { WritingHandoutView } from '@/components/writingHandout/WritingHandoutView'

const { Title, Text, Paragraph } = Typography
const { Search } = Input

function getQualityTag(status?: 'pending' | 'passed' | 'failed') {
  if (status === 'passed') {
    return <Tag color="green">质检通过</Tag>
  }
  if (status === 'failed') {
    return <Tag color="red">需重建</Tag>
  }
  return <Tag color="gold">待生成</Tag>
}

export function WritingPage() {
  const screens = Grid.useBreakpoint()
  const stacked = !screens.xl

  const [viewMode, setViewMode] = useState<'list' | 'handout'>('list')
  const [filters, setFilters] = useState<WritingFiltersResponse>({
    grades: [],
    semesters: [],
    exam_types: [],
    groups: [],
    major_categories: [],
    categories: [],
  })
  const [filter, setFilter] = useState<WritingFilter>({
    page: 1,
    size: 20,
  })
  const [loadingTemplates, setLoadingTemplates] = useState(false)
  const [loadingPapers, setLoadingPapers] = useState(false)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [templateTotal, setTemplateTotal] = useState(0)
  const [templates, setTemplates] = useState<WritingTemplateListItem[]>([])
  const [papers, setPapers] = useState<WritingTemplatePaperItem[]>([])
  const [detail, setDetail] = useState<WritingTemplatePaperDetailResponse | null>(null)
  const [selectedTemplateId, setSelectedTemplateId] = useState<number | null>(null)
  const [selectedPaperId, setSelectedPaperId] = useState<number | null>(null)
  const templateRequestSeq = useRef(0)
  const paperRequestSeq = useRef(0)
  const detailRequestSeq = useRef(0)

  useEffect(() => {
    loadFilters()
  }, [])

  useEffect(() => {
    loadTemplates()
  }, [filter])

  useEffect(() => {
    if (selectedTemplateId) {
      loadTemplatePapers(selectedTemplateId)
    } else {
      setPapers([])
      setSelectedPaperId(null)
      setDetail(null)
    }
  }, [selectedTemplateId])

  useEffect(() => {
    if (selectedTemplateId && selectedPaperId) {
      loadTemplatePaperDetail(selectedTemplateId, selectedPaperId)
    } else {
      setDetail(null)
    }
  }, [selectedTemplateId, selectedPaperId])

  const loadFilters = async () => {
    try {
      const response = await getWritingFilters()
      setFilters(response)
    } catch (error) {
      console.error('加载作文筛选项失败:', error)
      message.error('加载作文筛选项失败')
    }
  }

  const loadTemplates = async () => {
    const requestId = ++templateRequestSeq.current
    setLoadingTemplates(true)
    try {
      const response = await getWritingTemplates(filter)
      if (requestId !== templateRequestSeq.current) return
      setTemplates(response.items)
      setTemplateTotal(response.total)

      setSelectedTemplateId((current) => {
        if (current && response.items.some((item) => item.id === current)) {
          return current
        }
        return response.items[0]?.id ?? null
      })
    } catch (error) {
      if (requestId !== templateRequestSeq.current) return
      console.error('加载模板列表失败:', error)
      message.error('加载模板列表失败')
    } finally {
      if (requestId === templateRequestSeq.current) {
        setLoadingTemplates(false)
      }
    }
  }

  const loadTemplatePapers = async (templateId: number) => {
    const requestId = ++paperRequestSeq.current
    setLoadingPapers(true)
    try {
      const response = await getWritingTemplatePapers(templateId)
      if (requestId !== paperRequestSeq.current) return
      setPapers(response.papers)
      setSelectedPaperId((current) => {
        if (current && response.papers.some((item) => item.paper_id === current)) {
          return current
        }
        return response.papers[0]?.paper_id ?? null
      })
    } catch (error) {
      if (requestId !== paperRequestSeq.current) return
      console.error('加载模板试卷失败:', error)
      setPapers([])
      setSelectedPaperId(null)
      setDetail(null)
      message.error('加载模板试卷失败')
    } finally {
      if (requestId === paperRequestSeq.current) {
        setLoadingPapers(false)
      }
    }
  }

  const loadTemplatePaperDetail = async (templateId: number, paperId: number) => {
    const requestId = ++detailRequestSeq.current
    setLoadingDetail(true)
    try {
      const response = await getWritingTemplatePaperDetail(templateId, paperId)
      if (requestId !== detailRequestSeq.current) return
      setDetail(response)
    } catch (error) {
      if (requestId !== detailRequestSeq.current) return
      console.error('加载试卷范文详情失败:', error)
      setDetail(null)
      message.error('加载试卷范文详情失败')
    } finally {
      if (requestId === detailRequestSeq.current) {
        setLoadingDetail(false)
      }
    }
  }

  const availableMajorCategories = useMemo(() => {
    if (!filter.group_category_id) return filters.major_categories
    return filters.major_categories.filter((item) => item.parent_id === filter.group_category_id)
  }, [filters.major_categories, filter.group_category_id])

  const availableCategories = useMemo(() => {
    if (filter.major_category_id) {
      return filters.categories.filter((item) => item.parent_id === filter.major_category_id)
    }
    if (filter.group_category_id) {
      const majorIds = new Set(
        filters.major_categories
          .filter((item) => item.parent_id === filter.group_category_id)
          .map((item) => item.id)
      )
      return filters.categories.filter((item) => item.parent_id && majorIds.has(item.parent_id))
    }
    return filters.categories
  }, [filters.categories, filters.major_categories, filter.group_category_id, filter.major_category_id])

  const categoryTabItems = useMemo(
    () => [
      { key: 'all', label: '全部' },
      ...availableCategories.map((item) => ({ key: String(item.id), label: item.name })),
    ],
    [availableCategories]
  )

  const matchedDetailTasks = useMemo(() => {
    if (!detail) return []
    const currentCategoryId = detail.template.category.id
    return (detail.tasks || []).filter((task) => task.category?.id === currentCategoryId)
  }, [detail])

  useEffect(() => {
    if (!filter.category_id) return
    const exists = availableCategories.some((item) => item.id === filter.category_id)
    if (!exists) {
      setFilter((prev) => ({ ...prev, category_id: undefined, page: 1 }))
    }
  }, [availableCategories, filter.category_id])

  const templateColumns: ColumnsType<WritingTemplateListItem> = [
    {
      title: '分类',
      key: 'category',
      render: (_, record) => (
        <Space direction="vertical" size={4}>
          <Space wrap size={[4, 4]}>
            <Tag color="blue">{record.group_category.name}</Tag>
            <Tag color="cyan">{record.major_category.name}</Tag>
            <Tag color="geekblue">{record.category.name}</Tag>
          </Space>
          <Text strong>{record.template_name}</Text>
        </Space>
      ),
    },
    {
      title: '试卷',
      dataIndex: 'paper_count',
      width: 70,
      align: 'center',
    },
    {
      title: '题目',
      dataIndex: 'task_count',
      width: 70,
      align: 'center',
    },
    {
      title: '状态',
      dataIndex: 'quality_status',
      width: 96,
      align: 'center',
      render: (value) => getQualityTag(value),
    },
  ]

  const paperColumns: ColumnsType<WritingTemplatePaperItem> = [
    {
      title: '试卷',
      key: 'paper',
      render: (_, record) => (
        <Space direction="vertical" size={2}>
          <Text strong>{record.year || '-'} {record.region || ''}</Text>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {record.filename}
          </Text>
        </Space>
      ),
    },
    {
      title: '题目数',
      dataIndex: 'task_count',
      width: 88,
      align: 'center',
    },
  ]

  const renderTaskCard = (task: WritingTaskDetail, index: number) => {
    const sample: WritingSample | undefined = task.samples?.[0]
    return (
      <Card
        key={task.id}
        title={`当前试卷题目 ${index + 1} 正式范文`}
        size="small"
        extra={<Tag color="blue">150词左右</Tag>}
      >
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <div>
            <Text strong>题目</Text>
            <Paragraph style={{ whiteSpace: 'pre-wrap', marginTop: 8 }}>{task.task_content}</Paragraph>
          </div>

          {task.requirements && (
            <div>
              <Text strong>要求</Text>
              <Paragraph type="secondary" style={{ whiteSpace: 'pre-wrap', marginTop: 8 }}>
                {task.requirements}
              </Paragraph>
            </div>
          )}

          {sample ? (
            <>
              <div>
                <Space wrap>
                  <Tag color="green">当前试卷正式范文</Tag>
                  {getQualityTag(sample.quality_status)}
                  {sample.word_count ? <Tag>{sample.word_count} 词</Tag> : null}
                  {sample.generation_mode ? <Tag>{sample.generation_mode}</Tag> : null}
                </Space>
                <Paragraph style={{ whiteSpace: 'pre-wrap', marginTop: 8 }}>
                  {sample.sample_content}
                </Paragraph>
              </div>
              {sample.translation && (
                <div>
                  <Text strong>中文翻译</Text>
                  <Paragraph type="secondary" style={{ whiteSpace: 'pre-wrap', marginTop: 8 }}>
                    {sample.translation}
                  </Paragraph>
                </div>
              )}
            </>
          ) : (
            <Alert
              type="warning"
              showIcon
              message="当前题目的正式范文正在补齐"
              description="这道题会按当前子类的模板正文单独生成自己的正式范文。稍后刷新即可。"
            />
          )}
        </Space>
      </Card>
    )
  }

  return (
    <div style={{ padding: 24, height: '100%', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Radio.Group value={viewMode} onChange={(e) => setViewMode(e.target.value)} buttonStyle="solid">
          <Radio.Button value="list">
            <UnorderedListOutlined /> 模板视图
          </Radio.Button>
          <Radio.Button value="handout">
            <BookOutlined /> 讲义视图
          </Radio.Button>
        </Radio.Group>
      </div>

      {viewMode === 'handout' ? (
        <div style={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
          <WritingHandoutView />
        </div>
      ) : (
        <Space direction="vertical" size="large" style={{ width: '100%', flex: 1, minHeight: 0 }}>
          <Card>
            <Space direction="vertical" size="large" style={{ width: '100%' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 16, flexWrap: 'wrap' }}>
                <Space direction="vertical" size={6}>
                  <Title level={3} style={{ margin: 0 }}>
                    <FileTextOutlined style={{ marginRight: 8 }} />
                    作文汇编
                    <Badge count={templateTotal} style={{ marginLeft: 8 }} />
                  </Title>
                  <Text type="secondary">
                    先看模板，再看该模板覆盖的试卷，最后查看每道作文题按模板逐槽位生成的正式范文。
                  </Text>
                </Space>
                <Space wrap>
                  <Tag color="purple">一个子类一套模板</Tag>
                  <Tag color="green">一题一篇正式范文</Tag>
                  <Tag color="blue">导入即归类</Tag>
                </Space>
              </div>

              <Space wrap>
                <Select
                  allowClear
                  placeholder="年级"
                  style={{ width: 120 }}
                  value={filter.grade}
                  onChange={(value) => setFilter((prev) => ({ ...prev, grade: value, page: 1 }))}
                  options={filters.grades.map((item) => ({ value: item, label: item }))}
                />
                <Select
                  allowClear
                  placeholder="学期"
                  style={{ width: 120 }}
                  value={filter.semester}
                  onChange={(value) => setFilter((prev) => ({ ...prev, semester: value, page: 1 }))}
                  options={filters.semesters.map((item) => ({ value: item, label: `${item}学期` }))}
                />
                <Select
                  allowClear
                  placeholder="考试类型"
                  style={{ width: 120 }}
                  value={filter.exam_type}
                  onChange={(value) => setFilter((prev) => ({ ...prev, exam_type: value, page: 1 }))}
                  options={filters.exam_types.map((item) => ({ value: item, label: item }))}
                />
                <Select
                  allowClear
                  placeholder="文体组"
                  style={{ width: 120 }}
                  value={filter.group_category_id}
                  onChange={(value) => setFilter((prev) => ({
                    ...prev,
                    group_category_id: value,
                    major_category_id: undefined,
                    category_id: undefined,
                    page: 1,
                  }))}
                  options={filters.groups.map((item) => ({ value: item.id, label: item.name }))}
                />
                <Select
                  allowClear
                  placeholder="主类"
                  style={{ width: 160 }}
                  value={filter.major_category_id}
                  onChange={(value) => setFilter((prev) => ({
                    ...prev,
                    major_category_id: value,
                    category_id: undefined,
                    page: 1,
                  }))}
                  options={availableMajorCategories.map((item) => ({ value: item.id, label: item.name }))}
                />
                <Search
                  placeholder="搜索作文题目"
                  allowClear
                  style={{ width: 240 }}
                  onSearch={(value) => setFilter((prev) => ({ ...prev, search: value || undefined, page: 1 }))}
                />
              </Space>

              <Tabs
                activeKey={filter.category_id ? String(filter.category_id) : 'all'}
                items={categoryTabItems}
                onChange={(key) => setFilter((prev) => ({
                  ...prev,
                  category_id: key === 'all' ? undefined : Number(key),
                  page: 1,
                }))}
                tabBarStyle={{ marginBottom: 0 }}
              />
            </Space>
          </Card>

          <div style={{ flex: 1, minHeight: 0 }}>
            <Row gutter={16} style={{ height: '100%' }}>
              <Col span={stacked ? 24 : 8} style={{ display: 'flex' }}>
                <Card
                  title={<><ReadOutlined /> 模板列表</>}
                  style={{ width: '100%', height: '100%' }}
                  bodyStyle={{ padding: 0, height: stacked ? 'auto' : 'calc(100% - 57px)', display: 'flex', flexDirection: 'column' }}
                >
                  <Table
                    columns={templateColumns}
                    dataSource={templates}
                    rowKey="id"
                    loading={loadingTemplates}
                    pagination={{
                      current: filter.page,
                      pageSize: filter.size,
                      total: templateTotal,
                      onChange: (page, size) => setFilter((prev) => ({ ...prev, page, size })),
                      showSizeChanger: true,
                    }}
                    rowClassName={(record) => (record.id === selectedTemplateId ? 'ant-table-row-selected' : '')}
                    onRow={(record) => ({
                      onClick: () => {
                        setSelectedTemplateId(record.id)
                        setSelectedPaperId(null)
                        setDetail(null)
                      },
                      style: { cursor: 'pointer' },
                    })}
                    scroll={stacked ? undefined : { y: 'calc(100vh - 360px)' }}
                  />
                </Card>
              </Col>

              <Col span={stacked ? 24 : 6} style={{ display: 'flex' }}>
                <Card
                  title="模板下试卷"
                  style={{ width: '100%', height: '100%' }}
                  bodyStyle={{ padding: 0, height: stacked ? 'auto' : 'calc(100% - 57px)', display: 'flex', flexDirection: 'column' }}
                >
                  {!selectedTemplateId ? (
                    <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="先选择左侧模板" style={{ marginTop: 48 }} />
                  ) : (
                    <Table
                      columns={paperColumns}
                      dataSource={papers}
                      rowKey="paper_id"
                      loading={loadingPapers}
                      pagination={false}
                      rowClassName={(record) => (record.paper_id === selectedPaperId ? 'ant-table-row-selected' : '')}
                      onRow={(record) => ({
                        onClick: () => setSelectedPaperId(record.paper_id),
                        style: { cursor: 'pointer' },
                      })}
                      scroll={stacked ? undefined : { y: 'calc(100vh - 360px)' }}
                      locale={{ emptyText: '当前模板下暂无试卷' }}
                    />
                  )}
                </Card>
              </Col>

              <Col span={stacked ? 24 : 10} style={{ display: 'flex' }}>
                <Card
                  title="当前试卷题目正式范文"
                  style={{ width: '100%', height: '100%' }}
                  bodyStyle={{ height: stacked ? 'auto' : 'calc(100% - 57px)', overflow: 'auto' }}
                >
                  {loadingDetail ? (
                    <div style={{ textAlign: 'center', padding: 48 }}>
                      <Spin />
                    </div>
                  ) : !detail ? (
                    <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="选择中间试卷后查看题目范文" />
                  ) : (
                    <Space direction="vertical" size="large" style={{ width: '100%' }}>
                      <Card size="small" title={detail.template.template_name}>
                        <Descriptions size="small" column={1} bordered>
                          <Descriptions.Item label="分类路径">
                            {detail.template.category.path}
                          </Descriptions.Item>
                          <Descriptions.Item label="模板状态">
                            {getQualityTag(detail.template.quality_status)}
                          </Descriptions.Item>
                          <Descriptions.Item label="模板版本">
                            v{detail.template.template_version}
                          </Descriptions.Item>
                          <Descriptions.Item label="模板结构">
                            <Paragraph style={{ whiteSpace: 'pre-wrap', marginBottom: 0 }}>
                              {detail.template.structure || '未提供结构说明'}
                            </Paragraph>
                          </Descriptions.Item>
                          <Descriptions.Item label="模板正文">
                            <Paragraph style={{ whiteSpace: 'pre-wrap', marginBottom: 0 }}>
                              {detail.template.template_content}
                            </Paragraph>
                          </Descriptions.Item>
                          <Descriptions.Item label="试卷">
                            {detail.paper.year || '-'} {detail.paper.region || ''} {detail.paper.exam_type || ''} {detail.paper.filename || ''}
                          </Descriptions.Item>
                        </Descriptions>
                      </Card>

                      {matchedDetailTasks.length > 0 ? (
                        matchedDetailTasks.map((task, index) => renderTaskCard(task, index))
                      ) : (
                        <Alert
                          type="warning"
                          showIcon
                          message="当前试卷在该模板下没有匹配题目"
                          description="这张试卷可能同时包含多个子类的作文题。页面这里只会显示当前模板所属子类对应的题目。"
                        />
                      )}
                    </Space>
                  )}
                </Card>
              </Col>
            </Row>
          </div>
        </Space>
      )}
    </div>
  )
}
