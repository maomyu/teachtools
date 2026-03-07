/**
 * 高频词汇页面
 *
 * [INPUT]: 依赖 antd 组件、@/services/vocabularyService、@/types
 * [OUTPUT]: 对外提供 VocabularyPage 组件
 * [POS]: frontend/src/pages 的高频词库页面，支持多维筛选
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */
import { useState, useEffect, useCallback } from 'react'
import {
  Card,
  Table,
  Select,
  Input,
  Space,
  Tag,
  Typography,
  message,
  Button,
  InputNumber,
  Row,
  Col,
  Statistic,
  Empty,
} from 'antd'
import { SearchOutlined, ReloadOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'

import { getVocabulary, getVocabularyFilters } from '@/services/vocabularyService'
import type { Vocabulary, VocabularyFiltersResponse } from '@/types'
import { VocabularyDetailPanel } from '@/components/vocabulary/VocabularyDetailPanel'
import { PassageDetailContent } from '@/components/vocabulary/PassageDetailContent'

const { Text } = Typography
const { Search } = Input

export function VocabularyPage() {

  // ============================================================================
  //  状态管理
  // ============================================================================

  const [loading, setLoading] = useState(false)
  const [vocabulary, setVocabulary] = useState<Vocabulary[]>([])
  const [total, setTotal] = useState(0)
  const [filters, setFilters] = useState<VocabularyFiltersResponse>({
    grades: [],
    topics: [],
    years: [],
    regions: [],
    exam_types: [],
    semesters: [],
  })

  const [grade, setGrade] = useState<string | undefined>()
  const [topic, setTopic] = useState<string | undefined>()
  const [year, setYear] = useState<number | undefined>()
  const [region, setRegion] = useState<string | undefined>()
  const [examType, setExamType] = useState<string | undefined>()
  const [semester, setSemester] = useState<string | undefined>()
  const [minFrequency, setMinFrequency] = useState<number>(1)
  const [searchWord, setSearchWord] = useState<string | undefined>(undefined)

  const [page, setPage] = useState(1)
  const [size, setSize] = useState(50)

  const [selectedWord, setSelectedWord] = useState<Vocabulary | null>(null)
  const [panelOpen, setPanelOpen] = useState(false)

  // 抽屉状态
  const [passageDrawerOpen, setPassageDrawerOpen] = useState(false)
  const [viewingPassageId, setViewingPassageId] = useState<number | null>(null)
  const [viewingCharPosition, setViewingCharPosition] = useState<number | undefined>(undefined)

  // ============================================================================
  //  数据加载
  // ============================================================================

  useEffect(() => {
    loadFilters()
  }, [])

  useEffect(() => {
    loadVocabulary()
  }, [grade, topic, year, region, examType, semester, minFrequency, searchWord, page, size])

  const loadFilters = async () => {
    try {
      const data = await getVocabularyFilters()
      setFilters(data)
    } catch (error) {
      console.error('加载筛选项失败:', error)
    }
  }

  const loadVocabulary = useCallback(async () => {
    setLoading(true)
    try {
      const response = await getVocabulary({
        grade,
        topic,
        year,
        region,
        exam_type: examType,
        semester,
        min_frequency: minFrequency,
        search: searchWord || undefined,
        page,
        size,
      })
      setVocabulary(response.items)
      setTotal(response.total)
    } catch (error) {
      message.error('加载词汇失败')
      console.error(error)
    } finally {
      setLoading(false)
    }
  }, [grade, topic, year, region, examType, semester, minFrequency, searchWord, page, size])

  const handleSearch = (value: string) => {
    const trimmed = value.trim()
    setSearchWord(trimmed ? trimmed : undefined)
    setPage(1)
  }

  const handleReset = () => {
    setGrade(undefined)
    setTopic(undefined)
    setYear(undefined)
    setRegion(undefined)
    setExamType(undefined)
    setSemester(undefined)
    setMinFrequency(1)
    setSearchWord(undefined)
    setPage(1)
  }

  // 查看完整文章（打开抽屉）
  const handleViewFullPassage = useCallback((passageId: number, charPosition?: number) => {
    setViewingPassageId(passageId)
    setViewingCharPosition(charPosition)
    setPassageDrawerOpen(true)
  }, [])

  // 关闭抽屉
  const handleClosePassageDrawer = useCallback(() => {
    setPassageDrawerOpen(false)
  }, [])

  // ============================================================================
  //  表格配置
  // ============================================================================

  const columns: ColumnsType<Vocabulary> = [
    {
      title: '单词',
      dataIndex: 'word',
      key: 'word',
      width: 140,
      render: (word: string) => (
        <Text strong style={{ fontSize: 15 }}>
          {word}
        </Text>
      ),
    },
    {
      title: '释义',
      dataIndex: 'definition',
      key: 'definition',
      width: 180,
      ellipsis: true,
      render: (def: string) => def || <Text type="secondary">暂无释义</Text>,
    },
    {
      title: '词频',
      dataIndex: 'frequency',
      key: 'frequency',
      width: 80,
      sorter: (a, b) => a.frequency - b.frequency,
      render: (freq: number) => (
        <Tag color={freq >= 20 ? 'red' : freq >= 10 ? 'orange' : 'blue'}>
          {freq}
        </Tag>
      ),
    },
    {
      title: '例句预览',
      key: 'example',
      ellipsis: true,
      render: (_, record) => {
        const occ = record.occurrences?.[0]
        if (!occ) return <Text type="secondary">-</Text>
        const sentence = occ.sentence.length > 100
          ? occ.sentence.slice(0, 100) + '...'
          : occ.sentence
        return (
          <Text type="secondary" italic>
            "{sentence}"
          </Text>
        )
      },
    },
    {
      title: '年份',
      key: 'year',
      width: 80,
      render: (_, record) => {
        const years = new Set<number>()
        record.occurrences?.forEach(occ => {
          if (occ.year) years.add(occ.year)
        })
        if (years.size === 0) return <Text type="secondary">-</Text>
        return <Text>{Array.from(years).join(', ')}</Text>
      },
    },
    {
      title: '区县',
      key: 'region',
      width: 100,
      render: (_, record) => {
        const regions = new Set<string>()
        record.occurrences?.forEach(occ => {
          if (occ.region) regions.add(occ.region)
        })
        if (regions.size === 0) return <Text type="secondary">-</Text>
        const regionList = Array.from(regions).slice(0, 3)
        return (
          <Space direction="vertical" size={2}>
            {regionList.map((r, i) => (
              <Text key={i} style={{ fontSize: 12 }}>{r}</Text>
            ))}
            {regions.size > 3 && (
              <Text type="secondary" style={{ fontSize: 12 }}>
                +{regions.size - 3} 更多
              </Text>
            )}
          </Space>
        )
      },
    },
    {
      title: '年级',
      key: 'grade',
      width: 60,
      render: (_, record) => {
        const grades = new Set<string>()
        record.occurrences?.forEach(occ => {
          if (occ.grade) grades.add(occ.grade)
        })
        if (grades.size === 0) return <Text type="secondary">-</Text>
        return <Text>{Array.from(grades).join(', ')}</Text>
      },
    },
    {
      title: '考试类型',
      key: 'exam_type',
      width: 80,
      render: (_, record) => {
        const examTypes = new Set<string>()
        record.occurrences?.forEach(occ => {
          if (occ.exam_type) examTypes.add(occ.exam_type)
        })
        if (examTypes.size === 0) return <Text type="secondary">-</Text>
        return <Text>{Array.from(examTypes).join(', ')}</Text>
      },
    },
    {
      title: '学期',
      key: 'semester',
      width: 80,
      render: (_, record) => {
        const semesters = new Set<string>()
        record.occurrences?.forEach(occ => {
          if (occ.semester) semesters.add(`${occ.semester}学期`)
        })
        if (semesters.size === 0) return <Text type="secondary">-</Text>
        return <Text>{Array.from(semesters).join(', ')}</Text>
      },
    },
  ]

  const hasActiveFilters = grade || topic || year || region || examType || semester || minFrequency > 1

  // ============================================================================
  //  渲染
  // ============================================================================

  return (
    <div
      style={{
        display: 'flex',
        height: '100%',
        background: '#fff',
      }}
    >
      {/* 左侧:词汇表格区域 */}
      <div
        style={{
          flex: 1,
          minWidth: 0,
          display: 'flex',
          flexDirection: 'column',
          paddingRight: panelOpen ? 16 : 0,
          transition: 'padding-right 0.3s ease-in-out',
        }}
      >
        {/* 筛选区域 */}
        <Card style={{ marginBottom: 16 }}>
          <Row gutter={[16, 16]} align="middle">
            <Col>
              <Space>
                <Text type="secondary">筛选条件:</Text>

                <Select
                  placeholder="年级"
                  allowClear
                  style={{ width: 100 }}
                  value={grade}
                  onChange={setGrade}
                  options={filters.grades.map(g => ({ value: g, label: g }))}
                />

                <Select
                  placeholder="主题"
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
                  placeholder="年份"
                  allowClear
                  style={{ width: 100 }}
                  value={year}
                  onChange={setYear}
                  options={filters.years.map(y => ({ value: y, label: `${y}年` }))}
                />

                <Select
                  placeholder="区县"
                  allowClear
                  showSearch
                  style={{ width: 120 }}
                  value={region}
                  onChange={setRegion}
                  options={filters.regions.map(r => ({ value: r, label: r }))}
                  filterOption={(input, option) =>
                    (option?.label ?? '').includes(input)
                  }
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

                <InputNumber
                  placeholder="最低词频"
                  min={1}
                  max={100}
                  style={{ width: 100 }}
                  value={minFrequency}
                  onChange={(v) => setMinFrequency(v ?? 1)}
                />
              </Space>
            </Col>

            <Col flex="auto">
              <Search
                placeholder="搜索单词(精确匹配)..."
                allowClear
                style={{ maxWidth: 300 }}
                onSearch={handleSearch}
                enterButton={<SearchOutlined />}
              />
            </Col>

            <Col>
              <Button icon={<ReloadOutlined />} onClick={handleReset}>
                重置筛选
              </Button>
            </Col>
          </Row>

          {/* 统计信息 */}
          <Row gutter={32} style={{ marginTop: 16, paddingTop: 16, borderTop: '1px solid #f0f0f0' }}>
            <Col>
              <Statistic
                title={hasActiveFilters ? '筛选结果' : '词库总量'}
                value={total}
                suffix="个词汇"
                valueStyle={{ fontSize: 20 }}
              />
            </Col>
            {hasActiveFilters && (
              <Col>
                <Space>
                  {grade && <Tag color="blue" closable onClose={() => setGrade(undefined)}>{grade}</Tag>}
                  {topic && <Tag color="green" closable onClose={() => setTopic(undefined)}>{topic}</Tag>}
                  {year && <Tag color="orange" closable onClose={() => setYear(undefined)}>{year}年</Tag>}
                  {region && <Tag color="purple" closable onClose={() => setRegion(undefined)}>{region}</Tag>}
                  {examType && <Tag color="cyan" closable onClose={() => setExamType(undefined)}>{examType}</Tag>}
                  {semester && <Tag color="geekblue" closable onClose={() => setSemester(undefined)}>{semester}学期</Tag>}
                  {minFrequency > 1 && (
                    <Tag color="red" closable onClose={() => setMinFrequency(1)}>
                      词频 ≥ {minFrequency}
                    </Tag>
                  )}
                </Space>
              </Col>
            )}
          </Row>
        </Card>

        {/* 词汇表格 */}
        <div style={{ flex: 1, minHeight: 0 }}>
          <Card style={{ height: '100%' }}>
            <Table
              columns={columns}
              dataSource={vocabulary}
              rowKey="id"
              loading={loading}
              onRow={(record) => ({
                onClick: () => {
                  setSelectedWord(record)
                  setPanelOpen(true)
                  setPassageDrawerOpen(false)  // 切换词汇时关闭抽屉
                },
                style: { cursor: 'pointer' },
              })}
              locale={{
                emptyText: (
                  <Empty
                    description={hasActiveFilters ? '没有符合条件的词汇' : '暂无词汇数据,请先导入试卷'}
                  />
                ),
              }}
              pagination={{
                current: page,
                pageSize: size,
                total,
                showSizeChanger: true,
                showQuickJumper: true,
                pageSizeOptions: ['20', '50', '100', '200'],
                showTotal: (total, range) =>
                  `第 ${range[0]}-${range[1]} 个,共 ${total} 个`,
                onChange: (p, s) => {
                  setPage(p)
                  setSize(s)
                },
              }}
            />
          </Card>
        </div>
      </div>

      {/* 中间:词汇详情面板（例句列表） */}
      {panelOpen && selectedWord && (
        <div
          style={{
            width: 480,
            flexShrink: 0,
            height: '100%',
            overflow: 'hidden',
            borderLeft: '3px solid #1890ff',
            background: '#fff',
            display: 'flex',
            flexDirection: 'column',
            transition: 'all 0.3s ease',
          }}
        >
          <div
            style={{
              flex: 1,
              overflow: 'auto',
              padding: 16,
            }}
          >
            <VocabularyDetailPanel
              word={selectedWord}
              filters={{ grade, topic, year, region, exam_type: examType, semester }}
              onViewFullPassage={handleViewFullPassage}
            />
          </div>
          <div
            style={{
              padding: '12px 16px',
              borderTop: '1px solid #f0f0f0',
              textAlign: 'right',
            }}
          >
            <Button onClick={() => {
              setPanelOpen(false)
              setPassageDrawerOpen(false)
            }}>
              关闭
            </Button>
          </div>
        </div>
      )}

      {/* 右侧:完整文章抽屉 */}
      {passageDrawerOpen && viewingPassageId && (
        <div
          style={{
            width: 520,
            flexShrink: 0,
            height: '100%',
            overflow: 'hidden',
            borderLeft: '3px solid #52c41a',
            background: '#fafcff',
            display: 'flex',
            flexDirection: 'column',
            animation: 'slideIn 0.3s ease-out',
          }}
        >
          <div
            style={{
              flex: 1,
              overflow: 'auto',
              padding: 16,
            }}
          >
            <PassageDetailContent
              passageId={viewingPassageId}
              highlightWord={selectedWord?.word}
              charPosition={viewingCharPosition}
              onBack={handleClosePassageDrawer}
              showBackButton={true}
            />
          </div>
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
