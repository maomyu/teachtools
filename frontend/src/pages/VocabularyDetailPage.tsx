/**
 * 词汇详情页
 *
 * [INPUT]: 依赖 react-router-dom 的 useParams、 antd 组件
 * [OUTPUT]: 对外提供 VocabularyDetailPage 组件
 * [POS]: frontend/src/pages 的词汇详情页
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */
import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Card,
  List,
  Tag,
  Button,
  Typography,
  Space,
  message,
  Spin,
  Empty,
  Select,
} from 'antd'
import { ArrowLeftOutlined, BookOutlined } from '@ant-design/icons'

import { searchVocabulary } from '@/services/vocabularyService'
import type { VocabularyOccurrence } from '@/types'

const { Title, Text, Paragraph } = Typography

export function VocabularyDetailPage() {
  const { word } = useParams<{ word: string }>()
  const navigate = useNavigate()

  const [loading, setLoading] = useState(true)
  const [data, setData] = useState<{
    word: string
    definition?: string
    frequency: number
    occurrences: VocabularyOccurrence[]
  } | null>(null)

  // 筛选条件
  const [filterGrade, setFilterGrade] = useState<string>()

  useEffect(() => {
    if (word) {
    loadVocabularyDetail(decodeURIComponent(word))
  }
  }, [word])

  const loadVocabularyDetail = async (wordStr: string) => {
    setLoading(true)
    try {
      const result = await searchVocabulary(wordStr)
      setData(result)
    } catch (error) {
      message.error('加载词汇详情失败')
      console.error(error)
    } finally {
      setLoading(false)
    }
  }

  // 跳转到文章详情
  const handleGoToPassage = (passageId: number) => {
    navigate(`/reading/${passageId}`)
  }

  // 返回词汇列表
  const handleBack = () => {
    navigate('/vocabulary')
  }

  // 获取筛选后的出现位置
  const filteredOccurrences = data?.occurrences?.filter(occ => {
    // 如果没有筛选条件，返回所有
    if (!filterGrade) return true

    // 从 source 字段中提取年级信息进行筛选
    // source 格式: "2023 海淀 初一"
    const gradeInSource = occ.source?.split(' ')[2]
    return gradeInSource === filterGrade
  })

  // 提取所有年级（用于筛选）
  const grades = [...new Set(data?.occurrences?.map(o => o.source?.split(' ')[2]).filter(Boolean))]

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '100px 0' }}>
        <Spin size="large" />
      </div>
    )
  }

  if (!data) {
    return <Empty description="词汇不存在" />
  }

  return (
    <div>
      {/* 顶部 */}
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={handleBack}>
          返回列表
        </Button>
        <Title level={3} style={{ margin: 0 }}>
          <BookOutlined style={{ marginRight: 8 }} />
          {data.word}
        </Title>
        <Tag color="blue" style={{ fontSize: 14 }}>
          全局词频: {data.frequency} 次
        </Tag>
      </Space>

      {/* 词汇信息卡片 */}
      <Card style={{ marginBottom: 16 }}>
        <Space size="large">
          <div>
            <Text type="secondary">释义</Text>
            <Paragraph style={{ margin: '4px 0', fontSize: 16 }}>
              {data.definition || '暂无释义'}
            </Paragraph>
          </div>
        </Space>
      </Card>

      {/* 筛选区域 */}
      <Card size="small" style={{ marginBottom: 16 }}>
        <Space>
          <Text type="secondary">筛选条件:</Text>
          {grades.length > 0 && (
            <Select
              placeholder="年级"
              allowClear
              style={{ width: 120 }}
              value={filterGrade}
              onChange={setFilterGrade}
              options={grades.map(g => ({ value: g, label: g }))}
            />
          )}
        </Space>
      </Card>

      {/* 出现位置列表 */}
      <Card
        title={`出现位置 (${filteredOccurrences?.length || 0} 处)`}
      >
        {filteredOccurrences && filteredOccurrences.length > 0 ? (
          <List
            dataSource={filteredOccurrences}
            renderItem={(occ: VocabularyOccurrence) => (
              <List.Item
                style={{ cursor: 'pointer' }}
                onClick={() => handleGoToPassage(occ.passage_id)}
              >
                <Card
                  size="small"
                  style={{ marginBottom: 8 }}
                  hoverable
                >
                  <Space direction="vertical" style={{ width: '100%' }}>
                    {/* 出处信息 */}
                    <Space>
                      <Tag color="green">{occ.source || '未知出处'}</Tag>
                      <Text type="secondary">位置: {occ.char_position}</Text>
                    </Space>

                    {/* 例句 */}
                    <div
                      style={{
                        padding: '12px 16px',
                        background: '#fafafa',
                        borderRadius: 4,
                        marginTop: 8
                      }}
                    >
                      <Text italic style={{ fontSize: 14 }}>
                        "{occ.sentence}"
                      </Text>
                    </div>

                    {/* 操作按钮 */}
                    <Button
                      type="link"
                      style={{ marginTop: 8 }}
                    >
                        查看原文 →
                    </Button>
                  </Space>
                </Card>
              </List.Item>
            )}
          />
        ) : (
          <Empty description="暂无出现位置数据" />
        )}
      </Card>
    </div>
  )
}
