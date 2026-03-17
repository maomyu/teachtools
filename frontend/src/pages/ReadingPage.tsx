/**
 * 阅读文章列表页
 *
 * [INPUT]: 依赖 antd 组件、@/services/readingService、@/types
 * [OUTPUT]: 对外提供 ReadingPage 组件
 * [POS]: frontend/src/pages 的阅读文章列表页面
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
  Tabs,
  Badge,
} from 'antd'
import { SearchOutlined, EyeOutlined, DeleteOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'

import { getPassages, getTopics, deletePassage, batchDeletePassages } from '@/services/readingService'
import type { Passage, Topic, PassageFilter } from '@/types'

const { Title } = Typography
const { Search } = Input

export function ReadingPage() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [passages, setPassages] = useState<Passage[]>([])
  const [total, setTotal] = useState(0)
  const [cCount, setCCount] = useState(0)
  const [dCount, setDCount] = useState(0)
  const [topics, setTopics] = useState<Record<string, Topic[]>>({})

  // 文章类型筛选（C/D篇）
  const [passageType, setPassageType] = useState<'C' | 'D' | undefined>(undefined)

  // 批量选择状态
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])

  // 筛选条件
  const [filter, setFilter] = useState<PassageFilter>({
    page: 1,
    size: 20,
  })

  // 加载话题列表
  useEffect(() => {
    loadTopics()
  }, [])

  // 加载文章列表
  useEffect(() => {
    loadPassages()
  }, [filter, passageType])

  const loadTopics = async () => {
    try {
      const response = await getTopics()
      setTopics(response.topics_by_grade)
    } catch (error) {
      console.error('加载话题失败:', error)
    }
  }

  const loadPassages = async () => {
    setLoading(true)
    try {
      const response = await getPassages({
        ...filter,
        passage_type: passageType,
      })
      setPassages(response.items)
      setTotal(response.total)
      // 分别统计 C 篇和 D 篇数量
      setCCount(response.c_count || 0)
      setDCount(response.d_count || 0)
    } catch (error) {
      message.error('加载文章列表失败')
      console.error(error)
    } finally {
      setLoading(false)
    }
  }

  const handleView = (id: number) => {
    navigate(`/reading/${id}`)
  }

  const handleSearch = (value: string) => {
    setFilter({ ...filter, search: value, page: 1 })
  }

  const handleDelete = async (id: number) => {
    try {
      await deletePassage(id)
      message.success('删除成功')
      loadPassages()
    } catch (error) {
      message.error('删除失败')
      console.error(error)
    }
  }

  // 批量删除
  const handleBatchDelete = async () => {
    if (selectedRowKeys.length === 0) {
      message.warning('请选择要删除的文章')
      return
    }
    try {
      const result = await batchDeletePassages(selectedRowKeys as number[])
      message.success(result.message)
      setSelectedRowKeys([])
      loadPassages()
    } catch (error) {
      message.error('批量删除失败')
      console.error(error)
    }
  }

  // 表格行选择配置
  const rowSelection = {
    selectedRowKeys,
    onChange: (newSelectedRowKeys: React.Key[]) => {
      setSelectedRowKeys(newSelectedRowKeys)
    },
  }

  // Tab 切换处理
  const handleTabChange = (key: string) => {
    setPassageType(key === 'all' ? undefined : (key as 'C' | 'D'))
    setFilter({ ...filter, page: 1 })  // 切换 Tab 时重置分页
  }

  // 表格列定义
  const columns: ColumnsType<Passage> = [
    {
      title: '类型',
      dataIndex: 'passage_type',
      key: 'passage_type',
      width: 60,
      render: (type: string) => (
        <Tag color={type === 'C' ? 'blue' : 'green'}>{type}篇</Tag>
      ),
    },
    {
      title: '出处',
      key: 'source',
      width: 200,
      render: (_, record) => {
        const { source } = record
        if (!source) return '-'
        return (
          <span>
            {source.year} {source.region} {source.school} {source.grade} {source.exam_type}
          </span>
        )
      },
    },
    {
      title: '主话题',
      dataIndex: 'primary_topic',
      key: 'primary_topic',
      width: 120,
      render: (topic: string, record) => (
        <Space>
          <span>{topic || '-'}</span>
          {record.topic_verified && <Tag color="success">已校对</Tag>}
        </Space>
      ),
    },
    {
      title: '词数',
      dataIndex: 'word_count',
      key: 'word_count',
      width: 80,
      render: (count: number) => count || '-',
    },
    {
      title: '内容预览',
      dataIndex: 'content',
      key: 'content',
      ellipsis: true,
      render: (content: string) => content.slice(0, 100) + '...',
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
            title="确认删除"
            description="删除后无法恢复，确定要删除吗？"
            onConfirm={() => handleDelete(record.id)}
            okText="删除"
            cancelText="取消"
            okButtonProps={{ danger: true }}
          >
            <Button
              type="link"
              size="small"
              danger
              icon={<DeleteOutlined />}
            >
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  // 获取所有话题选项
  const getAllTopicOptions = () => {
    const options: Array<{ value: string; label: string }> = []
    for (const [grade, gradeTopics] of Object.entries(topics)) {
      options.push({
        value: `__grade_${grade}`,
        label: `── ${grade} ──`,
      })
      for (const topic of gradeTopics) {
        options.push({
          value: topic.name,
          label: `  ${topic.name}`,
        })
      }
    }
    return options
  }

  // Tab 配置
  const tabItems = [
    {
      key: 'all',
      label: (
        <Space size={4}>
          <span>全部</span>
          <Badge count={cCount + dCount} showZero style={{ backgroundColor: '#999' }} />
        </Space>
      ),
    },
    {
      key: 'C',
      label: (
        <Space size={4}>
          <span>C篇</span>
          <Badge count={cCount} showZero style={{ backgroundColor: '#1890ff' }} />
        </Space>
      ),
    },
    {
      key: 'D',
      label: (
        <Space size={4}>
          <span>D篇</span>
          <Badge count={dCount} showZero style={{ backgroundColor: '#52c41a' }} />
        </Space>
      ),
    },
  ]

  return (
    <div>
      <Title level={3}>阅读C/D篇</Title>

      {/* C/D 篇 Tab 切换 */}
      <Tabs
        activeKey={passageType || 'all'}
        onChange={handleTabChange}
        items={tabItems}
        style={{ marginBottom: 16 }}
      />

      <Card style={{ marginBottom: 16 }}>
        <Space wrap>
          {/* 批量删除按钮 */}
          {selectedRowKeys.length > 0 && (
            <Popconfirm
              title="批量删除确认"
              description={`确定要删除选中的 ${selectedRowKeys.length} 篇文章吗？此操作不可恢复。`}
              onConfirm={handleBatchDelete}
              okText="删除"
              cancelText="取消"
              okButtonProps={{ danger: true }}
            >
              <Button danger>
                批量删除 ({selectedRowKeys.length} 篇)
              </Button>
            </Popconfirm>
          )}
          <Select
            placeholder="选择年级"
            allowClear
            style={{ width: 120 }}
            value={filter.grade}
            onChange={(value) => setFilter({ ...filter, grade: value, page: 1 })}
            options={[
              { value: '初一', label: '初一' },
              { value: '初二', label: '初二' },
              { value: '初三', label: '初三' },
            ]}
          />
          <Select
            placeholder="选择话题"
            allowClear
            showSearch
            style={{ width: 200 }}
            value={filter.topic}
            onChange={(value) => setFilter({ ...filter, topic: value, page: 1 })}
            options={getAllTopicOptions()}
            filterOption={(input, option) =>
              (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
            }
          />
          <Select
            placeholder="选择年份"
            allowClear
            style={{ width: 120 }}
            value={filter.year}
            onChange={(value) => setFilter({ ...filter, year: value, page: 1 })}
            options={[
              { value: 2022, label: '2022' },
              { value: 2023, label: '2023' },
              { value: 2024, label: '2024' },
              { value: 2025, label: '2025' },
            ]}
          />
          <Search
            placeholder="搜索文章内容..."
            allowClear
            style={{ width: 300 }}
            onSearch={handleSearch}
            enterButton={<SearchOutlined />}
          />
        </Space>
      </Card>

      <Table
        columns={columns}
        dataSource={passages}
        rowKey="id"
        loading={loading}
        rowSelection={rowSelection}
        pagination={{
          current: filter.page,
          pageSize: filter.size,
          total,
          showSizeChanger: true,
          showTotal: (total) => `共 ${total} 篇`,
          onChange: (page, size) => setFilter({ ...filter, page, size }),
        }}
      />
    </div>
  )
}
