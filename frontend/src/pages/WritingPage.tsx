/**
 * 作文列表页
 *
 * [INPUT]: 依赖 antd 组件、@/services/writingService、@/types
 * [OUTPUT]: 对外提供 WritingPage 组件
 * [POS]: frontend/src/pages 的作文列表页面
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */
import { useState, useEffect, useMemo } from 'react'
import {
  Table,
  Card,
  Select,
  Input,
  Tabs,
  Tag,
  Space,
  Button,
  Typography,
  message,
  Popconfirm,
  Badge,
  Tooltip,
  Progress,
  Radio,
} from 'antd'
import {
  EyeOutlined,
  DeleteOutlined,
  RobotOutlined,
  FileTextOutlined,
  BookOutlined,
  UnorderedListOutlined,
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'

import {
  getWritings,
  getWritingFilters,
  deleteWriting,
  batchDeleteWritings,
  batchGenerateSamples,
} from '@/services/writingService'
import type { WritingTask, WritingFiltersResponse } from '@/types'
import { WritingHandoutView } from '@/components/writingHandout/WritingHandoutView'
import { WritingDetailContent } from '@/components/writing/WritingDetailContent'

const { Title } = Typography
const { Search } = Input

// 抽屉打开时要隐藏的次要列
const SECONDARY_COLUMN_KEYS = ['region', 'exam_type', 'semester', 'category_path', 'word_limit']

export function WritingPage() {
  const [viewMode, setViewMode] = useState<'list' | 'handout'>('list')
  const [loading, setLoading] = useState(false)
  const [writings, setWritings] = useState<WritingTask[]>([])
  const [total, setTotal] = useState(0)
  const [gradeCounts, setGradeCounts] = useState<Record<string, number>>({})
  const [filters, setFilters] = useState<WritingFiltersResponse>({
    grades: [],
    semesters: [],
    exam_types: [],
    groups: [],
    major_categories: [],
    categories: [],
  })

  // 批量选择状态
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])

  // 批量生成状态
  const [generating, setGenerating] = useState(false)
  const [generateProgress, setGenerateProgress] = useState({ current: 0, total: 0 })

  // 抽屉状态
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [selectedWritingId, setSelectedWritingId] = useState<number | null>(null)

  // 筛选条件
  const [filter, setFilter] = useState({
    page: 1,
    size: 20,
    grade: undefined as string | undefined,
    semester: undefined as string | undefined,
    exam_type: undefined as string | undefined,
    group_category_id: undefined as number | undefined,
    major_category_id: undefined as number | undefined,
    category_id: undefined as number | undefined,
    search: undefined as string | undefined,
  })

  // 加载筛选项
  useEffect(() => {
    loadFilters()
  }, [])

  // 加载作文列表
  useEffect(() => {
    loadWritings()
  }, [filter])

  const loadFilters = async () => {
    try {
      const response = await getWritingFilters()
      setFilters(response)
    } catch (error) {
      console.error('加载筛选项失败:', error)
    }
  }

  const loadWritings = async () => {
    setLoading(true)
    try {
      const response = await getWritings(filter)
      setWritings(response.items)
      setTotal(response.total)
      if (response.grade_counts) {
        setGradeCounts(response.grade_counts)
      }
    } catch (error) {
      message.error('加载作文列表失败')
      console.error(error)
    } finally {
      setLoading(false)
    }
  }

  // 打开抽屉查看详情
  const handleView = (id: number) => {
    setSelectedWritingId(id)
    setDrawerOpen(true)
  }

  // 关闭抽屉
  const handleCloseDrawer = () => {
    setDrawerOpen(false)
    setSelectedWritingId(null)
  }

  const handleSearch = (value: string) => {
    setFilter({ ...filter, search: value || undefined, page: 1 })
  }

  const handleDelete = async (id: number) => {
    try {
      await deleteWriting(id)
      message.success('删除成功')
      loadWritings()
    } catch (error) {
      message.error('删除失败')
      console.error(error)
    }
  }

  // 批量删除
  const handleBatchDelete = async () => {
    if (selectedRowKeys.length === 0) {
      message.warning('请选择要删除的作文')
      return
    }
    try {
      await batchDeleteWritings({ task_ids: selectedRowKeys as number[] })
      message.success('批量删除成功')
      setSelectedRowKeys([])
      loadWritings()
    } catch (error) {
      message.error('批量删除失败')
      console.error(error)
    }
  }

  // 批量生成范文
  const handleBatchGenerate = async () => {
    if (selectedRowKeys.length === 0) {
      message.warning('请选择要生成范文的作文')
      return
    }

    setGenerating(true)
    setGenerateProgress({ current: 0, total: selectedRowKeys.length })

    try {
      const result = await batchGenerateSamples({
        task_ids: selectedRowKeys as number[],
        score_level: '一档',
      })

      message.success(`成功生成 ${result.success_count} 篇范文，失败 ${result.fail_count} 篇`)
      setSelectedRowKeys([])
      loadWritings()
    } catch (error) {
      message.error('批量生成失败')
      console.error(error)
    } finally {
      setGenerating(false)
    }
  }

  // 表格行选择配置
  const rowSelection = {
    selectedRowKeys,
    onChange: (newSelectedRowKeys: React.Key[]) => {
      setSelectedRowKeys(newSelectedRowKeys)
    },
  }

  const getGroupColor = (type?: string) => {
    switch (type) {
      case '应用文':
        return 'blue'
      case '记叙文':
        return 'green'
      case '表达拓展类':
        return 'gold'
      default:
        return 'default'
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
      ...availableCategories.map((item) => ({
        key: String(item.id),
        label: item.name,
      })),
    ],
    [availableCategories]
  )

  useEffect(() => {
    if (!filter.category_id) return
    const categoryExists = availableCategories.some((item) => item.id === filter.category_id)
    if (!categoryExists) {
      setFilter((prev) => ({
        ...prev,
        category_id: undefined,
        page: 1,
      }))
    }
  }, [availableCategories, filter.category_id])

  // 表格列定义
  const columns: ColumnsType<WritingTask> = [
    {
      title: '年份',
      key: 'year',
      width: drawerOpen ? 60 : 80,
      render: (_, record) => record.source?.year || '-',
    },
    {
      title: '区县',
      key: 'region',
      width: 80,
      render: (_, record) => record.source?.region || '-',
    },
    {
      title: '学校',
      key: 'school',
      width: drawerOpen ? 100 : 120,
      ellipsis: true,
      render: (_, record) => (
        <Tooltip title={record.source?.school}>
          {record.source?.school || '-'}
        </Tooltip>
      ),
    },
    {
      title: '年级',
      dataIndex: 'grade',
      key: 'grade',
      width: drawerOpen ? 50 : 80,
      render: (grade: string) => grade || '-',
    },
    {
      title: '学期',
      dataIndex: 'semester',
      key: 'semester',
      width: 90,
      render: (semester: string) => semester || '-',
    },
    {
      title: '考试类型',
      dataIndex: 'exam_type',
      key: 'exam_type',
      width: 90,
      render: (examType: string) => examType || '-',
    },
    {
      title: '分类',
      key: 'category_path',
      width: drawerOpen ? 210 : 260,
      render: (_, record) => (
        <Space direction="vertical" size={4}>
          <Space wrap size={[4, 4]}>
            <Tag color={getGroupColor(record.group_category?.name)}>{record.group_category?.name || '未识别'}</Tag>
            {record.major_category?.name && <Tag color="cyan">{record.major_category.name}</Tag>}
            {record.category?.name && <Tag color="geekblue">{record.category.name}</Tag>}
          </Space>
          <span style={{ fontSize: 12, color: '#666' }}>
            目标：150词左右
          </span>
        </Space>
      ),
    },
    {
      title: '题目预览',
      dataIndex: 'task_content',
      key: 'task_content',
      ellipsis: true,
      render: (content: string) => (
        <Tooltip title={content}>
          {content?.slice(0, drawerOpen ? 40 : 80)}...
        </Tooltip>
      ),
    },
    {
      title: '字数',
      dataIndex: 'word_limit',
      key: 'word_limit',
      width: 80,
      render: (limit: string) => limit || '-',
    },
    {
      title: '操作',
      key: 'action',
      width: drawerOpen ? 80 : 150,
      render: (_, record) => (
        <Space>
          <Button
            type="link"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => handleView(record.id)}
          >
            {!drawerOpen && '查看'}
          </Button>
          {!drawerOpen && (
            <Popconfirm
              title="确定删除这篇作文吗？"
              onConfirm={() => handleDelete(record.id)}
              okText="确定"
              cancelText="取消"
            >
              <Button type="link" size="small" danger icon={<DeleteOutlined />}>
                删除
              </Button>
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ]

  // 响应式列：抽屉打开时隐藏次要列
  const visibleColumns = useMemo(() => {
    if (drawerOpen) {
      return columns.filter(col => !SECONDARY_COLUMN_KEYS.includes(col.key as string))
    }
    return columns
  }, [drawerOpen, columns])

  return (
    <div style={{ padding: 24, height: '100%', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
      {/* 视图切换器 */}
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Radio.Group
          value={viewMode}
          onChange={(e) => setViewMode(e.target.value)}
          buttonStyle="solid"
        >
          <Radio.Button value="list">
            <UnorderedListOutlined /> 列表视图
          </Radio.Button>
          <Radio.Button value="handout">
            <BookOutlined /> 讲义视图
          </Radio.Button>
        </Radio.Group>
      </div>

      {/* 讲义视图 */}
      {viewMode === 'handout' && (
        <div style={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
          <WritingHandoutView />
        </div>
      )}

      {/* 列表视图 + 抽屉的 flex 容器 */}
      {viewMode === 'list' && (
        <div style={{ display: 'flex', flex: 1, minHeight: 0, gap: drawerOpen ? 16 : 0 }}>
          {/* 左侧：列表 */}
          <div style={{
            flex: 1,
            minWidth: 0,
            transition: 'all 0.3s ease-in-out',
          }}>
            <Card>
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          {/* 标题和统计 */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 16, flexWrap: 'wrap' }}>
            <Space direction="vertical" size={6}>
              <Title level={3} style={{ margin: 0 }}>
                <FileTextOutlined style={{ marginRight: 8 }} />
                作文汇编
                <Badge count={total} style={{ marginLeft: 8 }} />
              </Title>
              <div style={{ color: '#667085', fontSize: 13 }}>
                试卷导入后自动完成子类归类，并为当前作文补齐子类模板与 150 词左右范文。
              </div>
            </Space>
            <Space wrap>
              {Object.entries(gradeCounts).map(([grade, count]) => (
                <Tag key={grade} color="blue">{grade}: {count}</Tag>
              ))}
              <Tag color="purple">子类模板驱动</Tag>
              <Tag color="green">导入即生成范文</Tag>
            </Space>
          </div>

          {/* 筛选器 */}
          <Space wrap>
            <Select
              allowClear
              placeholder="年级"
              style={{ width: 120 }}
              value={filter.grade}
              onChange={(value) => setFilter({ ...filter, grade: value, page: 1 })}
              options={filters.grades.map((g) => ({ value: g, label: g }))}
            />
            <Select
              allowClear
              placeholder="学期"
              style={{ width: 120 }}
              value={filter.semester}
              onChange={(value) => setFilter({ ...filter, semester: value, page: 1 })}
              options={filters.semesters.map((s) => ({ value: s, label: `${s}学期` }))}
            />
            <Select
              allowClear
              placeholder="考试类型"
              style={{ width: 120 }}
              value={filter.exam_type}
              onChange={(value) => setFilter({ ...filter, exam_type: value, page: 1 })}
              options={filters.exam_types.map((e) => ({ value: e, label: e }))}
            />
            <Select
              allowClear
              placeholder="文体组"
              style={{ width: 120 }}
              value={filter.group_category_id}
              onChange={(value) => setFilter({
                ...filter,
                group_category_id: value,
                major_category_id: undefined,
                category_id: undefined,
                page: 1,
              })}
              options={filters.groups.map((item) => ({ value: item.id, label: item.name }))}
            />
            <Select
              allowClear
              placeholder="主类"
              style={{ width: 160 }}
              value={filter.major_category_id}
              onChange={(value) => setFilter({
                ...filter,
                major_category_id: value,
                category_id: undefined,
                page: 1,
              })}
              options={availableMajorCategories.map((item) => ({ value: item.id, label: item.name }))}
            />
            <Search
              placeholder="搜索作文内容..."
              allowClear
              onSearch={handleSearch}
              style={{ width: 250 }}
            />
          </Space>

          <Tabs
            activeKey={filter.category_id ? String(filter.category_id) : 'all'}
            items={categoryTabItems}
            onChange={(activeKey) =>
              setFilter((prev) => ({
                ...prev,
                category_id: activeKey === 'all' ? undefined : Number(activeKey),
                page: 1,
              }))
            }
            tabBarStyle={{ marginBottom: 0 }}
          />

          {/* 批量操作栏 */}
          {selectedRowKeys.length > 0 && (
            <Card size="small" style={{ backgroundColor: '#f5f5f5' }}>
              <Space>
                <span>已选择 {selectedRowKeys.length} 篇</span>
                <Button
                  type="primary"
                  icon={<RobotOutlined />}
                  loading={generating}
                  onClick={handleBatchGenerate}
                >
                  批量生成范文
                </Button>
                {generating && (
                  <Progress
                    percent={Math.round((generateProgress.current / generateProgress.total) * 100)}
                    size="small"
                    style={{ width: 100 }}
                  />
                )}
                <Popconfirm
                  title={`确定删除选中的 ${selectedRowKeys.length} 篇作文吗？`}
                  onConfirm={handleBatchDelete}
                  okText="确定"
                  cancelText="取消"
                >
                  <Button danger icon={<DeleteOutlined />}>
                    批量删除
                  </Button>
                </Popconfirm>
                <Button onClick={() => setSelectedRowKeys([])}>取消选择</Button>
              </Space>
            </Card>
          )}

          {/* 表格 */}
          <Table
            rowSelection={rowSelection}
            columns={visibleColumns}
            dataSource={writings}
            rowKey="id"
            loading={loading}
            onRow={(record) => ({
              onClick: () => handleView(record.id),
              style: { cursor: 'pointer' },
            })}
            pagination={{
              current: filter.page,
              pageSize: filter.size,
              total,
              showSizeChanger: true,
              showTotal: (total) => `共 ${total} 篇`,
              onChange: (page, size) => setFilter({ ...filter, page, size }),
            }}
          />
        </Space>
      </Card>
          </div>

          {/* 抽屉面板 */}
          {drawerOpen && selectedWritingId && (
            <div
              style={{
                width: '70%',
                flexShrink: 0,
                height: '100%',
                overflow: 'hidden',
                borderLeft: '3px solid #1890ff',
                background: '#fafcff',
                display: 'flex',
                flexDirection: 'column',
                animation: 'slideIn 0.3s ease-out',
              }}
            >
              <WritingDetailContent
                writingId={selectedWritingId}
                onClose={handleCloseDrawer}
              />
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// CSS 动画
const style = document.createElement('style')
style.textContent = `
  @keyframes slideIn {
    from {
      transform: translateX(100%);
      opacity: 0;
    }
    to {
      transform: translateX(0);
      opacity: 1;
    }
  }
`
document.head.appendChild(style)
