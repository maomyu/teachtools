/**
 * 考点汇总页面
 *
 * [INPUT]: 依赖 antd 组件、@/services/clozeService、@/types、react-router-dom
 * [OUTPUT]: 对外提供 ClozePointsPage 组件
 * [POS]: frontend/src/pages 的考点汇总页面
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 *
 * 功能：
 * - 级联筛选器（大类 A-E → 具体考点 A1-E2）
 * - 快捷筛选标签（P1核心/高频等）
 * - URL 参数持久化（筛选条件可分享）
 * - 按年级、关键词搜索
 * - 展示考点词/短语、释义、出现次数
 * - 例句列表（含出处链接，可跳转到原文）
 */
import { useState, useEffect, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  Table,
  Select,
  Space,
  Tag,
  message,
  Card,
  Input,
  Button,
  Typography,
  Cascader,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'

import { getPointList, getClozeFilters, getPointTypesByCategory } from '@/services/clozeService'
import type { PointSummary, PointOccurrence, ClozeFiltersResponse, PointType, PointTypeByCategoryResponse } from '@/types'
import { CATEGORY_COLORS, ALL_POINT_TYPES, POINT_TYPE_BY_CODE } from '@/types'
import { ClozeDetailContent } from '@/components/cloze/ClozeDetailContent'

const { Text } = Typography

// ============================================================================
//  常量定义
// ============================================================================

// 考点编码到简称的映射
const POINT_CODE_TO_SHORT_NAME: Record<string, string> = {
  // A类-语篇理解
  A1: "上下文语义", A2: "复现照应", A3: "代词指代", A4: "情节顺序", A5: "情感态度",
  // B类-逻辑关系
  B1: "并列一致", B2: "转折对比", B3: "因果关系", B4: "其他逻辑",
  // C类-句法语法
  C1: "词性成分", C2: "固定搭配", C3: "语法形式",
  // D类-词汇选项
  D1: "词义辨析", D2: "熟词僻义",
  // E类-常识主题
  E1: "生活常识", E2: "主题共情",
}

// v1 旧系统颜色（向后兼容）
const POINT_TYPE_COLORS_V1: Record<string, string> = {
  '固定搭配': 'green',
  '词义辨析': 'orange',
  '熟词僻义': 'purple',
  '其他': 'default',
}

// ============================================================================
//  级联筛选器数据结构
// ============================================================================

/** 级联选择器选项：大类 → 具体考点 */
const POINT_CASCADER_OPTIONS = [
  {
    value: 'A',
    label: 'A 语篇理解类',
    children: ALL_POINT_TYPES
      .filter(pt => pt.category === 'A')
      .map(pt => ({ value: pt.code, label: `${pt.code} ${pt.name}` })),
  },
  {
    value: 'B',
    label: 'B 逻辑关系类',
    children: ALL_POINT_TYPES
      .filter(pt => pt.category === 'B')
      .map(pt => ({ value: pt.code, label: `${pt.code} ${pt.name}` })),
  },
  {
    value: 'C',
    label: 'C 句法语法类',
    children: ALL_POINT_TYPES
      .filter(pt => pt.category === 'C')
      .map(pt => ({ value: pt.code, label: `${pt.code} ${pt.name}` })),
  },
  {
    value: 'D',
    label: 'D 词汇选项类',
    children: ALL_POINT_TYPES
      .filter(pt => pt.category === 'D')
      .map(pt => ({ value: pt.code, label: `${pt.code} ${pt.name}` })),
  },
  {
    value: 'E',
    label: 'E 常识主题类',
    children: ALL_POINT_TYPES
      .filter(pt => pt.category === 'E')
      .map(pt => ({ value: pt.code, label: `${pt.code} ${pt.name}` })),
  },
]

/** 快捷筛选标签配置 */
const QUICK_FILTER_TAGS = [
  { key: 'P1', label: 'P1 核心考点', category: undefined, pointType: undefined, priority: 1 },
  { key: 'A', label: '语篇理解', category: 'A', pointType: undefined, priority: undefined },
  { key: 'B', label: '逻辑关系', category: 'B', pointType: undefined, priority: undefined },
  { key: 'D', label: '词汇选项', category: 'D', pointType: undefined, priority: undefined },
] as const

// 获取考点颜色（兼容新旧格式）
const getPointColor = (pointType: string, primaryPoint?: PointType): string => {
  // v2: 使用大类颜色
  if (primaryPoint?.category) {
    return CATEGORY_COLORS[primaryPoint.category] || 'default'
  }
  // v1: 使用旧类型颜色
  return POINT_TYPE_COLORS_V1[pointType] || 'default'
}

// 获取考点显示名称（兼容新旧格式）
const getPointLabel = (pointType: string, primaryPoint?: PointType): string => {
  // v2: 有 primary_point 对象，使用简称映射
  if (primaryPoint?.code) {
    return POINT_CODE_TO_SHORT_NAME[primaryPoint.code] || primaryPoint.name || primaryPoint.code
  }
  // v2: point_type 格式为 "D1 常规词义辨析"， 提取编码
  if (pointType && pointType.match(/^[A-E]\d\s/)) {
    const code = pointType.split(' ')[0]  // 提取 "D1"
    return POINT_CODE_TO_SHORT_NAME[code] || pointType
  }
  // v2: point_type 本身就是编码格式 (如 "A1", "B2")
  if (pointType && pointType.match(/^[A-E]\d$/)) {
    const def = POINT_TYPE_BY_CODE[pointType]
    return def ? `${pointType} ${def.name}` : POINT_CODE_TO_SHORT_NAME[pointType] || pointType
  }
  // v1: 使用旧类型（固定搭配/词义辨析/熟词僻义）
  return pointType
}

// 次要列（抽屉打开时隐藏）
const SECONDARY_COLUMN_KEYS = ['definition', 'occurrences', 'source']

// ============================================================================
//  主组件
// ============================================================================

export function ClozePointsPage() {
  // =========================================================================
  //  URL 参数持久化
  // =========================================================================
  const [searchParams, setSearchParams] = useSearchParams()

  // 从 URL 读取初始值
  const urlCategory = searchParams.get('cat') || undefined
  const urlPointType = searchParams.get('type') || undefined
  const urlPriority = searchParams.get('priority') ? Number(searchParams.get('priority')) : undefined
  const urlGrade = searchParams.get('grade') || undefined
  const urlKeyword = searchParams.get('q') || ''

  // =========================================================================
  //  状态管理
  // =========================================================================
  const [loading, setLoading] = useState(false)
  const [pointsList, setPointsList] = useState<PointSummary[]>([])
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

  // 筛选条件（从 URL 初始化）
  const [category, setCategory] = useState<string | undefined>(urlCategory)
  const [pointType, setPointType] = useState<string | undefined>(urlPointType)
  const [priority, setPriority] = useState<number | undefined>(urlPriority)
  const [grade, setGrade] = useState<string | undefined>(urlGrade)
  const [keyword, setKeyword] = useState<string>(urlKeyword)
  const [searchKeyword, setSearchKeyword] = useState<string>(urlKeyword)

  // v2 考点类型数据（按大类分组）- 预留用于未来扩展
  const [_pointTypesByCategory, setPointTypesByCategory] = useState<PointTypeByCategoryResponse>({} as PointTypeByCategoryResponse)

  // =========================================================================
  //  URL 同步
  // =========================================================================
  useEffect(() => {
    const params = new URLSearchParams()
    if (category) params.set('cat', category)
    if (pointType) params.set('type', pointType)
    if (priority) params.set('priority', String(priority))
    if (grade) params.set('grade', grade)
    if (searchKeyword) params.set('q', searchKeyword)
    setSearchParams(params, { replace: true })
  }, [category, pointType, priority, grade, searchKeyword, setSearchParams])

  // 分页
  const [page, setPage] = useState(1)
  const [size, setSize] = useState(20)

  // 抽屉状态
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [selectedClozeId, setSelectedClozeId] = useState<number | null>(null)
  const [selectedBlankNumber, setSelectedBlankNumber] = useState<number | null>(null)

  // 加载筛选项
  useEffect(() => {
    loadFilters()
    loadPointTypes()
  }, [])

  // 加载考点列表
  useEffect(() => {
    loadPointsList()
  }, [pointType, grade, searchKeyword, page, size])

  const loadFilters = async () => {
    try {
      const data = await getClozeFilters()
      setFilters(data)
    } catch (error) {
      console.error('加载筛选项失败:', error)
    }
  }

  const loadPointTypes = async () => {
    try {
      const data = await getPointTypesByCategory()
      setPointTypesByCategory(data)
    } catch (error) {
      console.error('加载考点类型失败:', error)
    }
  }

  const loadPointsList = async () => {
    setLoading(true)
    try {
      const response = await getPointList({
        point_type: pointType || undefined,
        category: !pointType ? category : undefined, // 大类筛选
        grade,
        keyword: searchKeyword || undefined,
        page,
        size,
      })
      setPointsList(response.items)
      setTotal(response.total)
    } catch (error) {
      message.error('加载考点列表失败')
      console.error(error)
    } finally {
      setLoading(false)
    }
  }

  // 搜索
  const handleSearch = () => {
    setSearchKeyword(keyword)
    setPage(1)
  }

  // 查看详情
  const handleViewDetail = (occurrence: PointOccurrence) => {
    // 从 source 字符串中解析出 clozeId
    // source 格式: "2024海淀区初一期中·完形"
    // 需要从后端返回中获取 cloze_id
    if (occurrence.passage_id) {
      setSelectedClozeId(occurrence.passage_id)
      setSelectedBlankNumber(occurrence.blank_number)
      setDrawerOpen(true)
    }
  }

  // 关闭抽屉
  const handleCloseDrawer = () => {
    setDrawerOpen(false)
    setSelectedClozeId(null)
    setSelectedBlankNumber(null)
  }

  // 表格列定义
  const columns: ColumnsType<PointSummary> = [
    {
      title: '考点词',
      dataIndex: 'word',
      key: 'word',
      width: 120,
      render: (word: string) => <Text strong style={{ fontSize: 14 }}>{word}</Text>,
    },
    {
      title: '释义',
      dataIndex: 'definition',
      key: 'definition',
      width: 200,
      ellipsis: true,
      render: (def: string) => def || '-',
    },
    {
      title: '类型',
      dataIndex: 'point_type',
      key: 'point_type',
      width: 100,
      render: (type: string, record) => {
        const primaryPoint = (record as any).primary_point
        const color = getPointColor(type, primaryPoint)
        const label = getPointLabel(type, primaryPoint)
        return (
          <Tag color={color}>
            {label}
          </Tag>
        )
      },
    },
    {
      title: '出现次数',
      dataIndex: 'frequency',
      key: 'frequency',
      width: 80,
      align: 'center',
      render: (freq: number) => <Tag color="blue">{freq}</Tag>,
    },
    {
      title: '例句',
      key: 'occurrences',
      render: (_, record) => {
        if (!record.occurrences?.length) return '-'
        return (
          <div style={{ maxHeight: 80, overflow: 'auto' }}>
            {record.occurrences.slice(0, 2).map((occ, idx) => (
              <div
                key={idx}
                style={{
                  marginBottom: 4,
                  padding: '4px 8px',
                  background: '#fafafa',
                  borderRadius: 4,
                  fontSize: 12,
                }}
              >
                <Text type="secondary" ellipsis style={{ maxWidth: 300 }}>
                  {occ.sentence}
                </Text>
              </div>
            ))}
            {record.occurrences.length > 2 && (
              <Text type="secondary" style={{ fontSize: 11 }}>
                +{record.occurrences.length - 2} 更多...
              </Text>
            )}
          </div>
        )
      },
    },
    {
      title: '出处',
      key: 'source',
      width: 180,
      render: (_, record) => {
        if (!record.occurrences?.length) return '-'
        const firstOcc = record.occurrences[0]
        return (
          <Text type="secondary" style={{ fontSize: 12 }}>
            {firstOcc.source}
          </Text>
        )
      },
    },
  ]

  // 响应式列（抽屉打开时只显示精简字段，且更紧凑）
  const visibleColumns = useMemo(() => {
    if (drawerOpen) {
      return columns
        .filter(col => !SECONDARY_COLUMN_KEYS.includes(col.key as string))
        .map(col => ({
          ...col,
          width: col.key === 'word' ? 80 : col.key === 'point_type' ? 75 : 55,
        }))
    }
    return columns
  }, [drawerOpen, columns])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: '#fff' }}>
      {/* 页面标题 */}
      <div style={{ padding: '16px 24px', borderBottom: '1px solid #f0f0f0' }}>
        <Text strong style={{ fontSize: 18 }}>考点汇总</Text>
        <Text type="secondary" style={{ marginLeft: 12, fontSize: 13 }}>
          共 {total} 个考点
        </Text>
      </div>

      {/* 筛选器 */}
      <Card style={{ marginBottom: 16, flexShrink: 0 }}>
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          {/* 快捷筛选标签 */}
          <Space wrap>
            {QUICK_FILTER_TAGS.map(tag => {
              const isActive = tag.priority !== undefined
                ? priority === tag.priority
                : tag.category !== undefined
                  ? category === tag.category && !pointType
                  : false
              return (
                <Tag
                  key={tag.key}
                  color={isActive ? 'blue' : 'default'}
                  style={{ cursor: 'pointer', padding: '2px 8px' }}
                  onClick={() => {
                    if (tag.priority !== undefined) {
                      // P1 核心考点：设置优先级，清除其他筛选
                      setPriority(isActive ? undefined : tag.priority)
                      setCategory(undefined)
                      setPointType(undefined)
                    } else if (tag.category !== undefined) {
                      // 大类标签：设置大类，清除具体考点
                      setCategory(isActive ? undefined : tag.category)
                      setPointType(undefined)
                      setPriority(undefined)
                    }
                    setPage(1)
                  }}
                >
                  {tag.label}
                </Tag>
              )
            })}
          </Space>

          {/* 详细筛选器 */}
          <Space wrap>
            {/* 级联筛选器：大类 → 具体考点 */}
            <Cascader
              placeholder="考点类型（大类/具体）"
              allowClear
              showSearch
              style={{ width: 220 }}
              value={pointType ? [pointType[0], pointType] : (category ? [category] : undefined)}
              options={POINT_CASCADER_OPTIONS}
              onChange={(value: (string | number)[]) => {
                if (!value || value.length === 0) {
                  // 清空
                  setCategory(undefined)
                  setPointType(undefined)
                } else if (value.length === 1) {
                  // 只选了大类
                  setCategory(value[0] as string)
                  setPointType(undefined)
                } else {
                  // 选了具体考点
                  setPointType(value[1] as string)
                  setCategory(value[0] as string)
                }
                setPage(1)
              }}
              changeOnSelect
              expandTrigger="hover"
            />
            {/* 优先级筛选 */}
            <Select
              placeholder="优先级"
              allowClear
              style={{ width: 120 }}
              value={priority}
              onChange={(val) => {
                setPriority(val)
                setPage(1)
              }}
              options={[
                { value: 1, label: 'P1 核心考点' },
                { value: 2, label: 'P2 重要考点' },
                { value: 3, label: 'P3 一般考点' },
              ]}
            />
            <Select
              placeholder="选择年级"
              allowClear
              style={{ width: 120 }}
              value={grade}
              onChange={(val) => {
                setGrade(val)
                setPage(1)
              }}
              options={filters.grades.map(g => ({ value: g, label: g }))}
            />
            <Input.Search
              placeholder="搜索考点词..."
              allowClear
              style={{ width: 200 }}
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              onSearch={handleSearch}
            />
            <Button type="primary" onClick={handleSearch}>
              搜索
            </Button>
          </Space>
        </Space>
      </Card>

      {/* 考点列表 */}
      <div style={{ display: 'flex', flex: 1, minHeight: 0 }}>
        {/* 左侧: 考点表格 */}
        <div style={{
          flex: 1,
          minWidth: 0,
          paddingRight: drawerOpen ? 16 : 0,
          transition: 'padding-right 0.3s ease-in-out'
        }}>
          <Table
            columns={visibleColumns}
            dataSource={pointsList}
            rowKey={(record) => `${record.word}-${record.point_type}`}
            loading={loading}
            onRow={(record) => ({
              onClick: () => {
                if (record.occurrences?.[0]?.passage_id) {
                  setSelectedClozeId(record.occurrences[0].passage_id)
                  setSelectedBlankNumber(record.occurrences[0].blank_number)
                  setDrawerOpen(true)
                }
              },
              style: { cursor: record.occurrences?.[0]?.passage_id ? 'pointer' : 'default' },
            })}
            pagination={{
              current: page,
              pageSize: size,
              total,
              showSizeChanger: true,
              showTotal: (total) => `共 ${total} 个考点`,
              onChange: (p, s) => {
                setPage(p)
                setSize(s)
              },
            }}
            expandable={{
              expandedRowRender: (record) => (
                <div style={{ padding: '8px 16px' }}>
                  <Text strong style={{ fontSize: 12, marginBottom: 8, display: 'block' }}>
                    出现位置 ({record.occurrences?.length || 0}次):
                  </Text>
                  {record.occurrences?.map((occ, idx) => (
                    <div
                      key={idx}
                      style={{
                        padding: '12px 16px',
                        marginBottom: 12,
                        background: '#fafafa',
                        borderRadius: 4,
                        borderLeft: '3px solid #1890ff',
                      }}
                    >
                      {/* 句子和出处 */}
                      <div style={{ marginBottom: 8 }}>
                        <Text style={{ fontSize: 13 }}>{occ.sentence}</Text>
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                        <Space>
                          <Tag color="blue" style={{ fontSize: 11 }}>第 {occ.blank_number} 空</Tag>
                          <Tag
                            color={getPointColor(occ.point_type, (occ as any).primary_point)}
                            style={{ fontSize: 11 }}
                          >
                            {getPointLabel(occ.point_type, (occ as any).primary_point)}
                          </Tag>
                          <Text type="secondary" style={{ fontSize: 11 }}>{occ.source}</Text>
                        </Space>
                        {occ.passage_id && (
                          <Button
                            type="link"
                            size="small"
                            onClick={() => handleViewDetail(occ)}
                          >
                            查看原文
                          </Button>
                        )}
                      </div>

                      {/* 根据考点类型展示不同的分析内容 */}
                      {occ.analysis && (
                        <div style={{ marginTop: 8, padding: '8px 12px', background: '#fff', borderRadius: 4 }}>
                          {/* 固定搭配 (v1: 固定搭配, v2: C2) */}
                          {(occ.point_type === '固定搭配' || (occ as any).primary_point?.code === 'C2') && occ.analysis.phrase && (
                            <>
                              <div style={{ marginBottom: 8 }}>
                                <Text strong style={{ color: '#52c41a' }}>短语：</Text>
                                <Text code>{occ.analysis.phrase}</Text>
                                {occ.analysis.confusion_words?.[0] && (
                                  <Text type="secondary"> - {occ.analysis.confusion_words[0].meaning}</Text>
                                )}
                              </div>
                              {occ.analysis.similar_phrases && occ.analysis.similar_phrases.length > 0 && (
                                <div style={{ marginBottom: 8 }}>
                                  <Text type="secondary" style={{ fontSize: 12 }}>相似短语：</Text>
                                  <Space size={4} wrap>
                                    {occ.analysis.similar_phrases.map((phrase, i) => (
                                      <Tag key={i} style={{ fontSize: 11 }}>{phrase}</Tag>
                                    ))}
                                  </Space>
                                </div>
                              )}
                            </>
                          )}

                          {/* 词义辨析 - 三维度分析 (v1: 词义辨析, v2: D1) */}
                          {(occ.point_type === '词义辨析' || (occ as any).primary_point?.code === 'D1') && occ.analysis.word_analysis && (
                            <>
                              {occ.analysis.dictionary_source && (
                                <div style={{ marginBottom: 8 }}>
                                  <Text type="secondary" style={{ fontSize: 11 }}>
                                    词典来源：{occ.analysis.dictionary_source}
                                  </Text>
                                </div>
                              )}
                              <div style={{ marginBottom: 8 }}>
                                <Text strong style={{ fontSize: 12, marginBottom: 4, display: 'block' }}>三维度分析：</Text>
                                <div style={{ overflowX: 'auto' }}>
                                  <table style={{ width: '100%', fontSize: 11, borderCollapse: 'collapse' }}>
                                    <thead>
                                      <tr style={{ background: '#f5f5f5' }}>
                                        <th style={{ padding: '4px 8px', border: '1px solid #e8e8e8', textAlign: 'left', whiteSpace: 'nowrap' }}>单词</th>
                                        <th style={{ padding: '4px 8px', border: '1px solid #e8e8e8', textAlign: 'left' }}>释义</th>
                                        <th style={{ padding: '4px 8px', border: '1px solid #e8e8e8', textAlign: 'left' }}>使用对象</th>
                                        <th style={{ padding: '4px 8px', border: '1px solid #e8e8e8', textAlign: 'left' }}>使用场景</th>
                                        <th style={{ padding: '4px 8px', border: '1px solid #e8e8e8', textAlign: 'left' }}>正负态度</th>
                                      </tr>
                                    </thead>
                                    <tbody>
                                      {Object.entries(occ.analysis.word_analysis).map(([word, data]) => (
                                        <tr key={word} style={{ background: word === record.word ? '#e6f7ff' : 'white' }}>
                                          <td style={{ padding: '4px 8px', border: '1px solid #e8e8e8', whiteSpace: 'nowrap' }}>
                                            <Text strong={word === record.word}>{word}</Text>
                                          </td>
                                          <td style={{ padding: '4px 8px', border: '1px solid #e8e8e8', maxWidth: 200 }}>
                                            <Text type="secondary" style={{ fontSize: 10 }}>{data.definition}</Text>
                                          </td>
                                          <td style={{ padding: '4px 8px', border: '1px solid #e8e8e8' }}>
                                            {data.dimensions?.使用对象 || '-'}
                                          </td>
                                          <td style={{ padding: '4px 8px', border: '1px solid #e8e8e8' }}>
                                            {data.dimensions?.使用场景 || '-'}
                                          </td>
                                          <td style={{ padding: '4px 8px', border: '1px solid #e8e8e8' }}>
                                            {data.dimensions?.正负态度 || '-'}
                                          </td>
                                        </tr>
                                      ))}
                                    </tbody>
                                  </table>
                                </div>
                              </div>
                            </>
                          )}

                          {/* 熟词僻义 (v1: 熟词僻义, v2: D2) */}
                          {(occ.point_type === '熟词僻义' || (occ as any).primary_point?.code === 'D2') && occ.analysis.textbook_meaning && (
                            <>
                              <div style={{ marginBottom: 8 }}>
                                <Text type="secondary" style={{ fontSize: 11 }}>课本出处：</Text>
                                <Text style={{ fontSize: 11 }}>{occ.analysis.textbook_source}</Text>
                              </div>
                              <div style={{ marginBottom: 8, display: 'flex', gap: 16 }}>
                                <div>
                                  <Text type="secondary" style={{ fontSize: 11 }}>课本释义：</Text>
                                  <Text style={{ fontSize: 11 }}>{occ.analysis.textbook_meaning}</Text>
                                </div>
                                <div>
                                  <Text type="secondary" style={{ fontSize: 11 }}>语境释义：</Text>
                                  <Text style={{ fontSize: 11, color: '#722ed1' }}>{occ.analysis.context_meaning}</Text>
                                </div>
                              </div>
                              {occ.analysis.similar_words && occ.analysis.similar_words.length > 0 && (
                                <div>
                                  <Text type="secondary" style={{ fontSize: 11 }}>其他熟词僻义示例：</Text>
                                  <div style={{ marginTop: 4 }}>
                                    {occ.analysis.similar_words.map((item, i) => (
                                      <Tag key={i} color="purple" style={{ fontSize: 10, marginBottom: 4 }}>
                                        {item.word}: {item.textbook} → {item.rare}
                                      </Tag>
                                    ))}
                                  </div>
                                </div>
                              )}
                            </>
                          )}

                          {/* 易混淆词（通用展示，非固定搭配时） */}
                          {occ.analysis.confusion_words && occ.analysis.confusion_words.length > 0 &&
                            occ.point_type !== '固定搭配' && (occ as any).primary_point?.code !== 'C2' && (
                            <div style={{ marginTop: 8 }}>
                              <Text type="secondary" style={{ fontSize: 11 }}>易混淆词：</Text>
                              <div style={{ marginTop: 4 }}>
                                {occ.analysis.confusion_words.map((item, i) => (
                                  <div key={i} style={{ marginBottom: 4, paddingLeft: 8, borderLeft: '2px solid #faad14' }}>
                                    <Text strong style={{ fontSize: 11 }}>{item.word}</Text>
                                    <Text type="secondary" style={{ fontSize: 11 }}> - {item.meaning}</Text>
                                    {item.reason && (
                                      <Text type="danger" style={{ fontSize: 10, marginLeft: 8 }}>
                                        ({item.reason})
                                      </Text>
                                    )}
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* 记忆技巧 */}
                          {occ.analysis.tips && (
                            <div style={{ marginTop: 8, padding: '4px 8px', background: '#fffbe6', borderRadius: 4 }}>
                              <Text type="secondary" style={{ fontSize: 11 }}>💡 {occ.analysis.tips}</Text>
                            </div>
                          )}

                          {/* 解析（兼容旧数据） */}
                          {!occ.analysis && occ.explanation && (
                            <div style={{ marginTop: 8 }}>
                              <Text type="secondary" style={{ fontSize: 11 }}>
                                解析: {occ.explanation}
                              </Text>
                            </div>
                          )}
                        </div>
                      )}

                      {/* 兼容旧数据：没有 analysis 对象但有 explanation */}
                      {!occ.analysis && occ.explanation && (
                        <div style={{ marginTop: 4 }}>
                          <Text type="secondary" style={{ fontSize: 11 }}>
                            解析: {occ.explanation}
                          </Text>
                        </div>
                      )}
                    </div>
                  ))}

                  {/* 聚合后的提示 */}
                  {record.tips && (
                    <div style={{ marginTop: 8, padding: '8px 12px', background: '#fffbe6', borderRadius: 4 }}>
                      <Text type="secondary" style={{ fontSize: 12 }}>💡 记忆技巧：{record.tips}</Text>
                    </div>
                  )}
                </div>
              ),
              rowExpandable: (record) => (record.occurrences?.length || 0) > 0,
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
                initialBlankNumber={selectedBlankNumber ?? undefined}
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
