/**
 * 阅读文章列表内容组件
 *
 * [INPUT]: 依赖 antd 组件、readingService、PassageDetailContent
 * [OUTPUT]: 对外提供 ReadingContent 组件
 * [POS]: frontend/src/pages 的阅读文章列表内容，用于 ReadingTabsPage
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */
import { useState, useEffect } from 'react'
import {
  Table,
  Card,
  Select,
  Input,
  Tag,
  Space,
  Button,
  message,
  Popconfirm,
} from 'antd'
import { SearchOutlined, DeleteOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'

import { getPassages, deletePassage, getPassageFilters } from '@/services/readingService'
import type { Passage, PassageFilter, PassageFiltersResponse } from '@/types'
import { PassageDetailContent } from '@/components/vocabulary/PassageDetailContent'

const { Search } = Input

export function ReadingContent() {
  const [loading, setLoading] = useState(false)
  const [passages, setPassages] = useState<Passage[]>([])
  const [total, setTotal] = useState(0)

  // 抽屉状态
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [selectedPassageId, setSelectedPassageId] = useState<number | null>(null)

  // 动态筛选项
  const [filterOptions, setFilterOptions] = useState<PassageFiltersResponse>({
    years: [],
    grades: [],
    exam_types: [],
    regions: [],
    topics: [],
    semesters: [],
  })

  // 筛选条件
  const [filter, setFilter] = useState<PassageFilter>({
    page: 1,
    size: 20,
  })

  // 加载筛选项
  useEffect(() => {
    loadFilterOptions()
  }, [])

  // 加载文章列表
  useEffect(() => {
    loadPassages()
  }, [filter])

  const loadFilterOptions = async () => {
    try {
      const response = await getPassageFilters()
      setFilterOptions(response)
    } catch (error) {
      console.error('加载筛选项失败:', error)
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

  // 打开文章详情抽屉
  const handleViewPassage = (passageId: number) => {
    setSelectedPassageId(passageId)
    setDrawerOpen(true)
  }

  // 关闭抽屉
  const handleCloseDrawer = () => {
    setDrawerOpen(false)
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
      title: '年份',
      key: 'year',
      width: 80,
      sorter: (a, b) => (a.source?.year || 0) - (b.source?.year || 0),
      render: (_, record) => record.source?.year || '-',
    },
    {
      title: '区县',
      key: 'region',
      width: 80,
      render: (_, record) => record.source?.region || '-',
    },
    {
      title: '年级',
      key: 'grade',
      width: 60,
      render: (_, record) => record.source?.grade || '-',
    },
    {
      title: '考试类型',
      key: 'exam_type',
      width: 90,
      render: (_, record) => record.source?.exam_type || '-',
    },
    {
      title: '学期',
      key: 'semester',
      width: 60,
      render: (_, record) => record.source?.semester ? `${record.source.semester}学期` : '-',
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
      width: 70,
      sorter: (a, b) => (a.word_count || 0) - (b.word_count || 0),
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
      width: 80,
      render: (_, record) => (
        <Popconfirm
          title="确认删除"
          description="删除后无法恢复，确定要删除吗？"
          onConfirm={(e) => {
            e?.stopPropagation()
            handleDelete(record.id)
          }}
          onCancel={(e) => e?.stopPropagation()}
          okText="删除"
          cancelText="取消"
          okButtonProps={{ danger: true }}
        >
          <Button
            type="link"
            size="small"
            danger
            icon={<DeleteOutlined />}
            onClick={(e) => e.stopPropagation()}
          >
            删除
          </Button>
        </Popconfirm>
      ),
    },
  ]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: '#fff' }}>
      <Card style={{ marginBottom: 16, flexShrink: 0 }}>
        <Space wrap>
          <Select
            placeholder="选择年级"
            allowClear
            style={{ width: 120 }}
            value={filter.grade}
            onChange={(value) => setFilter({ ...filter, grade: value, page: 1 })}
            options={filterOptions.grades.map(g => ({ value: g, label: g }))}
          />
          <Select
            placeholder="选择区县"
            allowClear
            style={{ width: 120 }}
            value={filter.region}
            onChange={(value) => setFilter({ ...filter, region: value, page: 1 })}
            options={filterOptions.regions.map(r => ({ value: r, label: r }))}
          />
          <Select
            placeholder="选择年份"
            allowClear
            style={{ width: 120 }}
            value={filter.year}
            onChange={(value) => setFilter({ ...filter, year: value, page: 1 })}
            options={filterOptions.years.map(y => ({ value: y, label: `${y}` }))}
          />
          <Select
            placeholder="考试类型"
            allowClear
            style={{ width: 120 }}
            value={filter.exam_type}
            onChange={(value) => setFilter({ ...filter, exam_type: value, page: 1 })}
            options={filterOptions.exam_types.map(e => ({ value: e, label: e }))}
          />
          <Select
            placeholder="学期"
            allowClear
            style={{ width: 100 }}
            value={filter.semester}
            onChange={(value) => setFilter({ ...filter, semester: value, page: 1 })}
            options={filterOptions.semesters.map(s => ({ value: s, label: `${s}学期` }))}
          />
          <Select
            placeholder="选择话题"
            allowClear
            showSearch
            style={{ width: 200 }}
            value={filter.topic}
            onChange={(value) => setFilter({ ...filter, topic: value, page: 1 })}
            options={filterOptions.topics.map(t => ({ value: t, label: t }))}
            filterOption={(input, option) =>
              (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
            }
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

      <div style={{ display: 'flex', flex: 1, minHeight: 0 }}>
        {/* 左侧: 文章表格 */}
        <div style={{ flex: 1, minWidth: 0, paddingRight: drawerOpen ? 16 : 0, transition: 'padding-right 0.3s ease-in-out' }}>
          <Table
            columns={columns}
            dataSource={passages}
            rowKey="id"
            loading={loading}
            onRow={(record) => ({
              onClick: () => handleViewPassage(record.id),
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
        </div>

        {/* 右侧: 文章详情抽屉 */}
        {drawerOpen && selectedPassageId && (
          <div
            style={{
              width: 520,
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
            <div style={{ flex: 1, overflow: 'auto', padding: 16 }}>
              <PassageDetailContent
                passageId={selectedPassageId}
                onBack={handleCloseDrawer}
                showBackButton={true}
              />
            </div>
          </div>
        )}
      </div>

      {/* CSS 动画 */}
      <style>{`
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
      `}</style>
    </div>
  )
}
