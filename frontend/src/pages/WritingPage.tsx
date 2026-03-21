/**
 * 作文列表页
 *
 * [INPUT]: 依赖 antd 组件、@/services/writingService、@/types
 * [OUTPUT]: 对外提供 WritingPage 组件
 * [POS]: frontend/src/pages 的作文列表页面
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Table,
  Card,
  Select,
  Input,
  Tag,
  Space,
  Button,
  Typography,
  message,
  Popconfirm,
  Badge,
  Tooltip,
  Progress,
} from 'antd'
import {
  SearchOutlined,
  EyeOutlined,
  DeleteOutlined,
  RobotOutlined,
  FileTextOutlined,
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

const { Title } = Typography
const { Search } = Input

export function WritingPage() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [writings, setWritings] = useState<WritingTask[]>([])
  const [total, setTotal] = useState(0)
  const [gradeCounts, setGradeCounts] = useState<Record<string, number>>({})
  const [filters, setFilters] = useState<WritingFiltersResponse>({
    grades: [],
    semesters: [],
    exam_types: [],
    writing_types: [],
    application_types: [],
    topics: [],
  })

  // 批量选择状态
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])

  // 批量生成状态
  const [generating, setGenerating] = useState(false)
  const [generateProgress, setGenerateProgress] = useState({ current: 0, total: 0 })

  // 筛选条件
  const [filter, setFilter] = useState({
    page: 1,
    size: 20,
    grade: undefined as string | undefined,
    semester: undefined as string | undefined,
    exam_type: undefined as string | undefined,
    writing_type: undefined as string | undefined,
    application_type: undefined as string | undefined,
    topic: undefined as string | undefined,
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

  const handleView = (id: number) => {
    navigate(`/writing/${id}`)
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

  // 文体类型颜色
  const getWritingTypeColor = (type: string) => {
    switch (type) {
      case '应用文':
        return 'blue'
      case '记叙文':
        return 'green'
      default:
        return 'default'
    }
  }

  // 表格列定义
  const columns: ColumnsType<WritingTask> = [
    {
      title: '年级',
      dataIndex: 'grade',
      key: 'grade',
      width: 80,
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
      title: '文体',
      dataIndex: 'writing_type',
      key: 'writing_type',
      width: 100,
      render: (type: string, record) => (
        <Space direction="vertical" size={0}>
          <Tag color={getWritingTypeColor(type)}>{type || '未识别'}</Tag>
          {record.application_type && (
            <span style={{ fontSize: 12, color: '#999' }}>{record.application_type}</span>
          )}
        </Space>
      ),
    },
    {
      title: '话题',
      dataIndex: 'primary_topic',
      key: 'primary_topic',
      width: 120,
      render: (topic: string) => topic || '-',
    },
    {
      title: '题目预览',
      dataIndex: 'task_content',
      key: 'task_content',
      ellipsis: true,
      render: (content: string) => (
        <Tooltip title={content}>
          {content?.slice(0, 80)}...
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
      width: 150,
      render: (_, record) => (
        <Space>
          <Button
            type="link"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => handleView(record.id)}
          >
            查看
          </Button>
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
        </Space>
      ),
    },
  ]

  return (
    <div style={{ padding: 24 }}>
      <Card>
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          {/* 标题和统计 */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Title level={3} style={{ margin: 0 }}>
              <FileTextOutlined style={{ marginRight: 8 }} />
              作文汇编
              <Badge count={total} style={{ marginLeft: 8 }} />
            </Title>
            <Space>
              {Object.entries(gradeCounts).map(([grade, count]) => (
                <Tag key={grade} color="blue">{grade}: {count}</Tag>
              ))}
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
              placeholder="文体"
              style={{ width: 120 }}
              value={filter.writing_type}
              onChange={(value) => setFilter({ ...filter, writing_type: value, page: 1 })}
              options={filters.writing_types.map((w) => ({ value: w, label: w }))}
            />
            <Select
              allowClear
              placeholder="应用文类型"
              style={{ width: 140 }}
              value={filter.application_type}
              onChange={(value) => setFilter({ ...filter, application_type: value, page: 1 })}
              options={filters.application_types.map((a) => ({ value: a, label: a }))}
            />
            <Select
              allowClear
              showSearch
              placeholder="话题"
              style={{ width: 150 }}
              value={filter.topic}
              onChange={(value) => setFilter({ ...filter, topic: value, page: 1 })}
              options={filters.topics.map((t) => ({ value: t, label: t }))}
              filterOption={(input, option) =>
                (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
              }
            />
            <Search
              placeholder="搜索作文内容..."
              allowClear
              onSearch={handleSearch}
              style={{ width: 250 }}
            />
          </Space>

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
            columns={columns}
            dataSource={writings}
            rowKey="id"
            loading={loading}
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
  )
}
