/**
 * 完形填空列表页面（抽屉式交互）
 *
 * [INPUT]: 依赖 antd 组件、@/services/clozeService、@/types
 * [OUTPUT]: 对外提供 ClozePage 组件
 * [POS]: frontend/src/pages 的完形文章列表页面
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */
import { useState, useEffect } from 'react'
import {
  Table,
  Select,
  Space,
  Tag,
  message,
  Card,
  Badge,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'

import { getClozeList, getClozeFilters } from '@/services/clozeService'
import type { ClozePassage, ClozeFiltersResponse, ClozeFilter } from '@/types'
import { ClozeDetailContent } from '@/components/cloze/ClozeDetailContent'

const POINT_TYPE_COLORS: Record<string, string> = {
  '固定搭配': 'green',
  '词义辨析': 'orange',
  '熟词僻义': 'purple',
  '词汇': 'blue',
}

export function ClozePage() {
  // ============================================================================
  //  状态管理
  // ============================================================================

  const [loading, setLoading] = useState(false)
  const [clozeList, setClozeList] = useState<ClozePassage[]>([])
  const [total, setTotal] = useState(0)
  const [filters, setFilters] = useState<ClozeFiltersResponse>({
    grades: [],
    topics: [],
    years: [],
    regions: [],
    exam_types: [],
    point_types: [],
    semesters: [],
  })

  const [grade, setGrade] = useState<string | undefined>()
  const [topic, setTopic] = useState<string | undefined>()
  const [pointType, setPointType] = useState<string | undefined>()
  const [examType, setExamType] = useState<string | undefined>()
  const [semester, setSemester] = useState<string | undefined>()
  const [region, setRegion] = useState<string | undefined>()
  const [year, setYear] = useState<number | undefined>()

  const [page, setPage] = useState(1)
  const [size, setSize] = useState(20)

  // 抽屉状态
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [selectedClozeId, setSelectedClozeId] = useState<number | null>(null)

  // ============================================================================
  //  数据加载
  // ============================================================================

  useEffect(() => {
    loadFilters()
  }, [])

  useEffect(() => {
    loadClozeList()
  }, [grade, topic, pointType, examType, semester, region, year, page, size])

  const loadFilters = async () => {
    try {
      const data = await getClozeFilters()
      setFilters(data)
    } catch (error) {
      console.error('加载筛选项失败:', error)
    }
  }

  const loadClozeList = async () => {
    setLoading(true)
    try {
      const params: ClozeFilter = {
        grade,
        topic,
        point_type: pointType,
        exam_type: examType,
        semester,
        region,
        year,
        page,
        size,
      }
      const response = await getClozeList(params)
      setClozeList(response.items)
      setTotal(response.total)
    } catch (error) {
      message.error('加载完形列表失败')
      console.error(error)
    } finally {
      setLoading(false)
    }
  }

  // 打开详情抽屉
  const handleViewCloze = (clozeId: number) => {
    setSelectedClozeId(clozeId)
    setDrawerOpen(true)
  }

  // 关闭抽屉
  const handleCloseDrawer = () => {
    setDrawerOpen(false)
  }

  // ============================================================================
  //  表格列定义（参考阅读模块）
  // ============================================================================

  const columns: ColumnsType<ClozePassage> = [
    {
      title: '年份',
      key: 'year',
      width: 80,
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
      width: 70,
      render: (_, record) => record.source?.grade || '-',
    },
    {
      title: '考试类型',
      key: 'exam_type',
      width: 80,
      render: (_, record) => record.source?.exam_type || '-',
    },
    {
      title: '学期',
      key: 'semester',
      width: 70,
      render: (_, record) => record.source?.semester ? `${record.source.semester}学期` : '-',
    },
    {
      title: '主话题',
      dataIndex: 'primary_topic',
      key: 'topic',
      width: 120,
      render: (topic: string) => topic ? <Tag color="blue">{topic}</Tag> : '-',
    },
    {
      title: '词数',
      dataIndex: 'word_count',
      key: 'word_count',
      width: 70,
      render: (count: number) => count || '-',
    },
    {
      title: '空格数',
      key: 'blank_count',
      width: 80,
      align: 'center',
      render: (_, record) => (
        <Badge
          count={record.points?.length || 0}
          showZero
          style={{ backgroundColor: '#1890ff' }}
        />
      ),
    },
    {
      title: '考点分布',
      key: 'point_distribution',
      render: (_, record) => {
        if (!record.points?.length) return '-'
        const dist: Record<string, number> = {}
        record.points.forEach(p => {
          if (p.point_type) {
            dist[p.point_type] = (dist[p.point_type] || 0) + 1
          }
        })
        if (Object.keys(dist).length === 0) return '-'
        return (
          <Space wrap size={[4, 4]}>
            {Object.entries(dist).map(([type, count]) => (
              <Tag key={type} color={POINT_TYPE_COLORS[type] || 'default'}>
                {type} ({count})
              </Tag>
            ))}
          </Space>
        )
      },
    },
  ]

  // ============================================================================
  //  渲染
  // ============================================================================

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: '#fff' }}>
      {/* 筛选器 */}
      <Card style={{ marginBottom: 16, flexShrink: 0 }}>
        <Space wrap>
          <Select
            placeholder="选择年级"
            allowClear
            style={{ width: 120 }}
            value={grade}
            onChange={setGrade}
            options={filters.grades.map(g => ({ value: g, label: g }))}
          />
          <Select
            placeholder="选择区县"
            allowClear
            style={{ width: 120 }}
            value={region}
            onChange={setRegion}
            options={filters.regions.map(r => ({ value: r, label: r }))}
          />
          <Select
            placeholder="选择年份"
            allowClear
            style={{ width: 100 }}
            value={year}
            onChange={setYear}
            options={filters.years.map(y => ({ value: y, label: `${y}` }))}
          />
          <Select
            placeholder="考试类型"
            allowClear
            style={{ width: 100 }}
            value={examType}
            onChange={setExamType}
            options={filters.exam_types.map(e => ({ value: e, label: e }))}
          />
          <Select
            placeholder="学期"
            allowClear
            style={{ width: 100 }}
            value={semester}
            onChange={setSemester}
            options={filters.semesters.map(s => ({ value: s, label: `${s}学期` }))}
          />
          <Select
            placeholder="选择话题"
            allowClear
            showSearch
            style={{ width: 160 }}
            value={topic}
            onChange={setTopic}
            options={filters.topics.map(t => ({ value: t, label: t }))}
            filterOption={(input, option) =>
              (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
            }
          />
          <Select
            placeholder="考点类型"
            allowClear
            style={{ width: 120 }}
            value={pointType}
            onChange={setPointType}
            options={filters.point_types.map(t => ({ value: t, label: t }))}
          />
        </Space>
      </Card>

      {/* 内容区：表格 + 抽屉 */}
      <div style={{ display: 'flex', flex: 1, minHeight: 0 }}>
        {/* 左侧: 文章表格 */}
        <div style={{ flex: 1, minWidth: 0, paddingRight: drawerOpen ? 16 : 0, transition: 'padding-right 0.3s ease-in-out' }}>
          <Table
            columns={columns}
            dataSource={clozeList}
            rowKey="id"
            loading={loading}
            onRow={(record) => ({
              onClick: () => handleViewCloze(record.id),
              style: { cursor: 'pointer' },
            })}
            pagination={{
              current: page,
              pageSize: size,
              total,
              showSizeChanger: true,
              showTotal: (total) => `共 ${total} 篇`,
              onChange: (p, s) => {
                setPage(p)
                setSize(s)
              },
            }}
          />
        </div>

        {/* 右侧: 详情抽屉 */}
        {drawerOpen && selectedClozeId && (
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
              <ClozeDetailContent
                clozeId={selectedClozeId}
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
