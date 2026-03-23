/**
 * 完形填空列表页面（抽屉式交互 + 视图切换）
 *
 * [INPUT]: 依赖 antd 组件、@/services/clozeService、@/types
 * [OUTPUT]: 对外提供 ClozePage 组件
 * [POS]: frontend/src/pages 的完形文章列表页面
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */
import { useState, useEffect, useMemo } from 'react'
import {
  Table,
  Select,
  Space,
  Tag,
  message,
  Card,
  Badge,
  Radio,
  Button,
  Popconfirm,
  Cascader,
} from 'antd'
import { UnorderedListOutlined, BookOutlined, DeleteOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'

import { getClozeList, getClozeFilters, deleteCloze, batchDeleteClozes } from '@/services/clozeService'
import type { ClozePassage, ClozeFiltersResponse, ClozeFilter } from '@/types'
import { CATEGORY_COLORS, POINT_TYPE_BY_CODE, ALL_POINT_TYPES } from '@/types'
import { ClozeDetailContent } from '@/components/cloze/ClozeDetailContent'
import { ClozeHandoutView } from '@/components/clozeHandout/ClozeHandoutView'

// 次要列（抽屉打开时隐藏）
const SECONDARY_COLUMN_KEYS = ['region', 'school', 'exam_type', 'semester', 'topic', 'word_count', 'point_distribution']

// ============================================================================
//  考点类型级联筛选器
// ============================================================================

const POINT_CASCADER_OPTIONS = [
  { value: 'A', label: 'A 语篇理解类', children: ALL_POINT_TYPES.filter(pt => pt.category === 'A').map(pt => ({ value: pt.code, label: `${pt.code} ${pt.name}` })) },
  { value: 'B', label: 'B 逻辑关系类', children: ALL_POINT_TYPES.filter(pt => pt.category === 'B').map(pt => ({ value: pt.code, label: `${pt.code} ${pt.name}` })) },
  { value: 'C', label: 'C 句法语法类', children: ALL_POINT_TYPES.filter(pt => pt.category === 'C').map(pt => ({ value: pt.code, label: `${pt.code} ${pt.name}` })) },
  { value: 'D', label: 'D 词汇选项类', children: ALL_POINT_TYPES.filter(pt => pt.category === 'D').map(pt => ({ value: pt.code, label: `${pt.code} ${pt.name}` })) },
  { value: 'E', label: 'E 常识主题类', children: ALL_POINT_TYPES.filter(pt => pt.category === 'E').map(pt => ({ value: pt.code, label: `${pt.code} ${pt.name}` })) },
]

export function ClozePage() {
  // ============================================================================
  //  状态管理
  // ============================================================================

  // 视图模式：列表视图 / 讲义视图
  const [viewMode, setViewMode] = useState<'list' | 'handout'>('list')

  const [loading, setLoading] = useState(false)
  const [clozeList, setClozeList] = useState<ClozePassage[]>([])
  const [total, setTotal] = useState(0)
  const [filters, setFilters] = useState<ClozeFiltersResponse>({
    grades: [],
    topics: [],
    years: [],
    regions: [],
    schools: [],
    exam_types: [],
    point_types: [],
    semesters: [],
  })

  const [grade, setGrade] = useState<string | undefined>()
  const [topic, setTopic] = useState<string | undefined>()
  const [category, setCategory] = useState<string | undefined>()
  const [pointType, setPointType] = useState<string | undefined>()
  const [examType, setExamType] = useState<string | undefined>()
  const [semester, setSemester] = useState<string | undefined>()
  const [region, setRegion] = useState<string | undefined>()
  const [school, setSchool] = useState<string | undefined>()
  const [year, setYear] = useState<number | undefined>()

  const [page, setPage] = useState(1)
  const [size, setSize] = useState(20)

  // 抽屉状态
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [selectedClozeId, setSelectedClozeId] = useState<number | null>(null)

  // 批量选择状态
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])

  // ============================================================================
  //  数据加载
  // ============================================================================

  useEffect(() => {
    loadFilters()
  }, [])

  useEffect(() => {
    loadClozeList()
  }, [grade, topic, pointType, category, examType, semester, region, school, year, page, size])

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
        category,
        exam_type: examType,
        semester,
        region,
        school,
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
    setSelectedClozeId(null)
  }

  // 单条删除
  const handleDeleteCloze = async (id: number) => {
    try {
      await deleteCloze(id)
      message.success('删除成功')
      loadClozeList()
    } catch (error) {
      message.error('删除失败')
      console.error(error)
    }
  }

  // 批量删除
  const handleBatchDelete = async () => {
    if (selectedRowKeys.length === 0) {
      message.warning('请选择要删除的完形文章')
      return
    }
    try {
      const result = await batchDeleteClozes(selectedRowKeys as number[])
      message.success(result.message)
      setSelectedRowKeys([])
      loadClozeList()
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

  // ============================================================================
  //  表格列定义
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
      title: '学校',
      key: 'school',
      width: 100,
      render: (_, record) => record.source?.school || '-',
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
          // V2: 使用 primary_point_code 字段（字符串），V1: 兼容 point_type
          const code = (p as any).primary_point_code || p.point_type
          if (code) {
            dist[code] = (dist[code] || 0) + 1
          }
        })
        if (Object.keys(dist).length === 0) return '-'
        return (
          <Space wrap size={[4, 4]}>
            {Object.entries(dist).map(([code, count]) => {
            // 根据编码首字母获取大类颜色
            const category = code[0] || 'A'
            const color = CATEGORY_COLORS[category] || 'default'
            const displayName = POINT_TYPE_BY_CODE[code]?.name || code
            return (
              <Tag key={code} color={color}>
                {code} {displayName} ({count})
              </Tag>
            )
          })}
          </Space>
        )
      },
    },
    {
      title: '操作',
      key: 'action',
      width: 100,
      render: (_, record) => (
        <Space>
          <Button
            type="link"
            size="small"
            onClick={(e) => {
              e.stopPropagation()
              handleViewCloze(record.id)
            }}
          >
            查看
          </Button>
          <Popconfirm
            title="确认删除"
            description="删除后无法恢复，确定要删除吗？"
            onConfirm={(e) => {
              e?.stopPropagation()
              handleDeleteCloze(record.id)
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
        </Space>
      ),
    },
  ]

  // 响应式列（抽屉打开时只显示精简字段，且更紧凑）
  const visibleColumns = useMemo(() => {
    if (drawerOpen) {
      return columns
        .filter(col => !SECONDARY_COLUMN_KEYS.includes(col.key as string))
        .map(col => ({
          ...col,
          width: col.key === 'year' ? 50 : col.key === 'grade' ? 50 : 55,
        }))
    }
    return columns
  }, [drawerOpen, columns])

  // ============================================================================
  //  渲染
  // ============================================================================

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: '#fff' }}>
      {/* 视图切换 + 筛选器 */}
      <Card style={{ marginBottom: 16, flexShrink: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          {/* 筛选器 */}
          <Space wrap>
            {/* 批量删除按钮 */}
            {selectedRowKeys.length > 0 && (
              <Popconfirm
                title="批量删除确认"
                description={`确定要删除选中的 ${selectedRowKeys.length} 篇完形文章吗？此操作不可恢复。`}
                onConfirm={handleBatchDelete}
                okText="删除"
                cancelText="取消"
                okButtonProps={{ danger: true }}
              >
                <Button danger icon={<DeleteOutlined />}>
                  批量删除 ({selectedRowKeys.length} 篇)
                </Button>
              </Popconfirm>
            )}
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
              placeholder="选择学校"
              allowClear
              showSearch
              style={{ width: 160 }}
              value={school}
              onChange={setSchool}
              options={filters.schools.map(s => ({ value: s, label: s }))}
              filterOption={(input, option) =>
                (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
              }
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
            <Cascader
              placeholder="考点类型（大类/具体）"
              allowClear
              showSearch
              style={{ width: 200 }}
              value={pointType ? [pointType[0], pointType] : (category ? [category] : undefined)}
              options={POINT_CASCADER_OPTIONS}
              onChange={(value: (string | number)[]) => {
                if (!value || value.length === 0) {
                  setCategory(undefined)
                  setPointType(undefined)
                } else if (value.length === 1) {
                  setCategory(value[0] as string)
                  setPointType(undefined)
                } else {
                  setCategory(value[0] as string)
                  setPointType(value[1] as string)
                }
                setPage(1)
              }}
              changeOnSelect
              expandTrigger="hover"
            />
          </Space>

          {/* 视图切换器 */}
          <Radio.Group
            value={viewMode}
            onChange={(e) => setViewMode(e.target.value)}
            buttonStyle="solid"
            size="small"
          >
            <Radio.Button value="list">
              <Space size={4}>
                <UnorderedListOutlined />
                列表视图
              </Space>
            </Radio.Button>
            <Radio.Button value="handout">
              <Space size={4}>
                <BookOutlined />
                讲义视图
              </Space>
            </Radio.Button>
          </Radio.Group>
        </div>
      </Card>

      {/* 根据视图模式显示不同内容 */}
      {viewMode === 'list' ? (
        /* 列表视图 */
        <div style={{ display: 'flex', flex: 1, minHeight: 0 }}>
          {/* 左侧: 文章表格 */}
          <div style={{
            flex: 1,
            minWidth: 0,
            paddingRight: drawerOpen ? 16 : 0,
            transition: 'padding-right 0.3s ease-in-out'
          }}>
            <Table
              columns={visibleColumns}
              dataSource={clozeList}
              rowKey="id"
              loading={loading}
              rowSelection={rowSelection}
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
      ) : (
        /* 讲义视图 */
        <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
          <ClozeHandoutView />
        </div>
      )}

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
