/**
 * 考点汇总页面
 *
 * [INPUT]: 依赖 antd 组件、@/services/clozeService、@/types
 * [OUTPUT]: 对外提供 ClozePointsPage 组件
 * [POS]: frontend/src/pages 的考点汇总页面
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 *
 * 功能：
 * - 按考点类型筛选（固定搭配/词义辨析/熟词僻义）
 * - 按年级、关键词搜索
 * - 展示考点词/短语、释义、出现次数
 * - 例句列表（含出处链接，可跳转到原文）
 */
import { useState, useEffect, useMemo } from 'react'
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
} from 'antd'
import type { ColumnsType } from 'antd/es/table'

import { getPointList, getClozeFilters } from '@/services/clozeService'
import type { PointSummary, PointOccurrence, ClozeFiltersResponse } from '@/types'
import { ClozeDetailContent } from '@/components/cloze/ClozeDetailContent'

const { Text } = Typography

// ============================================================================
//  常量定义
// ============================================================================

const POINT_TYPE_COLORS: Record<string, string> = {
  '固定搭配': 'green',
  '词义辨析': 'orange',
  '熟词僻义': 'purple',
  '其他': 'default',
}

const POINT_TYPE_OPTIONS = [
  { value: '固定搭配', label: '固定搭配' },
  { value: '词义辨析', label: '词义辨析' },
  { value: '熟词僻义', label: '熟词僻义' },
]

// 次要列（抽屉打开时隐藏）
const SECONDARY_COLUMN_KEYS = ['definition', 'occurrences', 'source']

// ============================================================================
//  主组件
// ============================================================================

export function ClozePointsPage() {
  // 状态管理
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

  // 筛选条件
  const [pointType, setPointType] = useState<string | undefined>()
  const [grade, setGrade] = useState<string | undefined>()
  const [keyword, setKeyword] = useState<string>('')
  const [searchKeyword, setSearchKeyword] = useState<string>('')

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

  const loadPointsList = async () => {
    setLoading(true)
    try {
      const response = await getPointList({
        point_type: pointType,
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
      render: (type: string) => (
        <Tag color={POINT_TYPE_COLORS[type] || 'default'}>
          {type}
        </Tag>
      ),
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
        <Space wrap>
          <Select
            placeholder="考点类型"
            allowClear
            style={{ width: 120 }}
            value={pointType}
            onChange={setPointType}
            options={POINT_TYPE_OPTIONS}
          />
          <Select
            placeholder="选择年级"
            allowClear
            style={{ width: 120 }}
            value={grade}
            onChange={setGrade}
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
                          <Tag color={POINT_TYPE_COLORS[occ.point_type] || 'default'} style={{ fontSize: 11 }}>
                            {occ.point_type}
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
                          {/* 固定搭配 */}
                          {occ.point_type === '固定搭配' && occ.analysis.phrase && (
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

                          {/* 词义辨析 - 三维度分析 */}
                          {occ.point_type === '词义辨析' && occ.analysis.word_analysis && (
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
                                        <th style={{ padding: '4px 8px', border: '1px solid #e8e8e8', textAlign: 'left' }}>排除理由</th>
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
                                          <td style={{ padding: '4px 8px', border: '1px solid #e8e8e8', color: '#ff4d4f' }}>
                                            {data.rejection_reason || '-'}
                                          </td>
                                        </tr>
                                      ))}
                                    </tbody>
                                  </table>
                                </div>
                              </div>
                            </>
                          )}

                          {/* 熟词僻义 */}
                          {occ.point_type === '熟词僻义' && occ.analysis.textbook_meaning && (
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

                          {/* 易混淆词（通用展示） */}
                          {occ.analysis.confusion_words && occ.analysis.confusion_words.length > 0 && occ.point_type !== '固定搭配' && (
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
