/**
 * 高频词汇页面
 *
 * [INPUT]: 依赖 antd 组件、@/services/vocabularyService、@/types
 * [OUTPUT]: 对外提供 VocabularyPage 组件
 * [POS]: frontend/src/pages 的高频词库页面，支持多维筛选
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */
import { useState, useEffect, useCallback, useMemo } from 'react'
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
  Empty,
} from 'antd'
import { SearchOutlined, ReloadOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'

import { getVocabulary, getVocabularyFilters } from '@/services/vocabularyService'
import type { Vocabulary, VocabularyFiltersResponse } from '@/types'
import { VocabularyDetailPanel } from '@/components/vocabulary/VocabularyDetailPanel'
import { PassageDetailContent } from '@/components/vocabulary/PassageDetailContent'
import { ClozeDetailContent } from '@/components/cloze/ClozeDetailContent'

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
    sources: [],
  })

  const [grade, setGrade] = useState<string | undefined>()
  const [topic, setTopic] = useState<string | undefined>()
  const [year, setYear] = useState<number | undefined>()
  const [region, setRegion] = useState<string | undefined>()
  const [examType, setExamType] = useState<string | undefined>()
  const [semester, setSemester] = useState<string | undefined>()
  const [minFrequency, setMinFrequency] = useState<number>(1)
  const [searchWord, setSearchWord] = useState<string | undefined>(undefined)
  const [source, setSource] = useState<string | undefined>(undefined)

  const [page, setPage] = useState(1)
  const [size, setSize] = useState(50)

  const [selectedWord, setSelectedWord] = useState<Vocabulary | null>(null)
  const [panelOpen, setPanelOpen] = useState(false)

  // 抽屉状态
  const [passageDrawerOpen, setPassageDrawerOpen] = useState(false)

  // 响应式面板宽度状态
  const [panelWidth, setPanelWidth] = useState(480)
  const [drawerWidth, setDrawerWidth] = useState(520)
  const [viewingPassageId, setViewingPassageId] = useState<number | null>(null)
  const [viewingCharPosition, setViewingCharPosition] = useState<number | undefined>(undefined)
  const [viewingSourceType, setViewingSourceType] = useState<'reading' | 'cloze' | null>(null)

  // ============================================================================
  //  数据加载
  // ============================================================================

  useEffect(() => {
    loadFilters()
  }, [])

  useEffect(() => {
    loadVocabulary()
  }, [grade, topic, year, region, examType, semester, minFrequency, searchWord, source, page, size])

  // 响应式面板宽度计算 - 优化：减小面板宽度，让表格获得更多空间
  useEffect(() => {
    const calculatePanelWidths = () => {
      const containerWidth = window.innerWidth
      // 小屏幕下更紧凑
      if (containerWidth < 1200) {
        setPanelWidth(340)
        setDrawerWidth(380)
      } else if (containerWidth < 1400) {
        setPanelWidth(360)
        setDrawerWidth(400)
      } else {
        setPanelWidth(400)
        setDrawerWidth(450)
      }
    }

    calculatePanelWidths()
    window.addEventListener('resize', calculatePanelWidths)
    return () => window.removeEventListener('resize', calculatePanelWidths)
  }, [])

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
        source: source as 'reading' | 'cloze' | 'all' | undefined,
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
  }, [grade, topic, year, region, examType, semester, minFrequency, searchWord, source, page, size])

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
    setSource(undefined)
    setPage(1)
  }

  // 查看完整文章(打开抽屉) - 词汇详情面板会自动向左偏移
  const handleViewFullPassage = useCallback((passageId: number, charPosition?: number, sourceType?: 'reading' | 'cloze') => {
    setViewingPassageId(passageId)
    setViewingCharPosition(charPosition)
    setViewingSourceType(sourceType || 'reading')
    setPassageDrawerOpen(true)
  }, [])

  // 关闭抽屉 - 同时关闭词汇详情面板
  const handleClosePassageDrawer = useCallback(() => {
    setPassageDrawerOpen(false)
    setPanelOpen(false)
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
      title: '来源',
      key: 'sources',
      width: 100,
      render: (_, record) => {
        if (!record.sources || record.sources.length === 0) return <Text type="secondary">-</Text>
        return (
          <Space size={4}>
            {record.sources.map(s => (
              <Tag key={s} color={s === '阅读' ? 'blue' : 'green'} style={{ margin: 0 }}>
                {s}
              </Tag>
            ))}
          </Space>
        )
      },
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

  // 次要列 - 当面板/抽屉打开时自动隐藏
  // 保留: word(单词), frequency(词频), sources(来源)
  // 隐藏: definition(释义), example(例句), year(年份), region(区县), grade(年级), exam_type(考试类型), semester(学期)
  const secondaryColumnKeys = ['definition', 'example', 'year', 'region', 'grade', 'exam_type', 'semester']

  // 响应式列 - 根据面板状态过滤次要列
  const visibleColumns = useMemo(() => {
    if (panelOpen || passageDrawerOpen) {
      return columns.filter(col => !secondaryColumnKeys.includes(col.key as string))
    }
    return columns
  }, [panelOpen, passageDrawerOpen, columns])

  const hasActiveFilters = grade || topic || year || region || examType || semester || minFrequency > 1 || source

  // ============================================================================
  //  渲染
  // ============================================================================

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: 'calc(100vh - 64px - 40px)', // 减去 Header(64px) + Content padding(40px)
        background: '#fff',
        overflow: 'hidden',
      }}
    >
      {/* 筛选区域 - 顶层，不受推开效果影响 */}
      <Card style={{ marginBottom: 16, flexShrink: 0 }}>
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

                <Select
                  placeholder="来源"
                  allowClear
                  style={{ width: 100 }}
                  value={source}
                  onChange={setSource}
                  options={[
                    { value: 'all', label: '全部' },
                    { value: 'reading', label: '阅读' },
                    { value: 'cloze', label: '完形' },
                  ]}
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
              <Space>
                <Button icon={<ReloadOutlined />} onClick={handleReset}>
                  重置筛选
                </Button>
                <Tag color="blue" style={{ fontSize: 13, padding: '2px 8px' }}>
                  共 {total} 个词汇
                </Tag>
              </Space>
            </Col>

            {/* 已选筛选条件标签 */}
            {hasActiveFilters && (
              <Col>
                <Space size={4}>
                  {grade && <Tag color="blue" closable onClose={() => setGrade(undefined)}>{grade}</Tag>}
                  {topic && <Tag color="green" closable onClose={() => setTopic(undefined)}>{topic}</Tag>}
                  {year && <Tag color="orange" closable onClose={() => setYear(undefined)}>{year}年</Tag>}
                  {region && <Tag color="purple" closable onClose={() => setRegion(undefined)}>{region}</Tag>}
                  {examType && <Tag color="cyan" closable onClose={() => setExamType(undefined)}>{examType}</Tag>}
                  {semester && <Tag color="geekblue" closable onClose={() => setSemester(undefined)}>{semester}学期</Tag>}
                  {source && <Tag color="cyan" closable onClose={() => setSource(undefined)}>{source === 'reading' ? '阅读' : source === 'cloze' ? '完形' : '全部'}</Tag>}
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

      {/* 主内容区 - row flex，推开效果只影响这里 */}
      <div style={{ display: 'flex', flex: 1, minHeight: 0, overflow: 'hidden' }}>
        {/* 左侧:词汇表格区域 */}
        <div style={{
          flex: 1,
          minWidth: 0,
          paddingRight: panelOpen ? 16 : 0,
          transition: 'padding-right 0.3s ease-in-out',
          overflow: 'auto',
        }}>
          <Card style={{ height: '100%' }}>
            <Table
              columns={visibleColumns}
              dataSource={vocabulary}
              rowKey="id"
              loading={loading}
              onRow={(record) => ({
                onClick: () => {
                  // Toggle 行为：点击已选中行则关闭面板，否则切换到新词汇
                  if (selectedWord?.id === record.id && panelOpen) {
                    setPanelOpen(false)
                    setPassageDrawerOpen(false)
                  } else {
                    setSelectedWord(record)
                    setPanelOpen(true)
                    setPassageDrawerOpen(false)
                  }
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

        {/* 词汇详情面板 - 在主内容区 row flex 内部，与表格并列 */}
        {panelOpen && selectedWord && (
          <div
            style={{
              width: panelWidth,
              flexShrink: 0,
              height: '100%',
              overflow: 'hidden',
              borderLeft: '3px solid #1890ff',
              boxShadow: '-4px 0 16px rgba(0, 0, 0, 0.12)',
              background: '#fff',
            }}
          >
            <VocabularyDetailPanel
              word={selectedWord}
              filters={{ grade, topic, year, region, exam_type: examType, semester }}
              onViewFullPassage={handleViewFullPassage}
            />
          </div>
        )}

        {/* 文章抽屉 - 在主内容区 row flex 内部，与表格和词汇详情面板并列 */}
        {passageDrawerOpen && viewingPassageId && viewingSourceType && (
          <div
            style={{
              width: drawerWidth,
              flexShrink: 0,
              height: '100%',
              overflow: 'auto',
              borderLeft: viewingSourceType === 'reading' ? '3px solid #52c41a' : '3px solid #722ed1',
              background: '#fafcff',
              padding: 12,
              animation: 'slideIn 0.3s ease-out',
            }}
          >
            {viewingSourceType === 'reading' ? (
              <PassageDetailContent
                passageId={viewingPassageId}
                highlightWord={selectedWord?.word}
                charPosition={viewingCharPosition}
                onBack={handleClosePassageDrawer}
                showBackButton={true}
              />
            ) : (
              <ClozeDetailContent
                clozeId={viewingPassageId}
                highlightWord={selectedWord?.word}
                charPosition={viewingCharPosition}
                onBack={handleClosePassageDrawer}
                showBackButton={true}
              />
            )}
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
