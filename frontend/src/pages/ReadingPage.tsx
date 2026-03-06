/**
 * 阅读文章列表页
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
} from 'antd'
import { SearchOutlined, EyeOutlined, DeleteOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'

import { getPassages, getTopics, deletePassage } from '@/services/readingService'
import type { Passage, Topic, PassageFilter } from '@/types'

const { Title } = Typography
const { Search } = Input

export function ReadingPage() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [passages, setPassages] = useState<Passage[]>([])
  const [total, setTotal] = useState(0)
  const [topics, setTopics] = useState<Record<string, Topic[]>>({})

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
  }, [filter])

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
      const response = await getPassages(filter)
      setPassages(response.items)
      setTotal(response.total)
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
            {source.year} {source.region} {source.grade} {source.exam_type}
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

  return (
    <div>
      <Title level={3}>阅读C/D篇</Title>

      <Card style={{ marginBottom: 16 }}>
        <Space wrap>
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
