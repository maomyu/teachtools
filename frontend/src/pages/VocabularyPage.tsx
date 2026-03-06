/**
 * 高频词汇页面
 */
import { useState, useEffect } from 'react'
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
  Modal,
} from 'antd'
import { SearchOutlined, EyeOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'

import { getVocabulary, searchVocabulary } from '@/services/vocabularyService'
import type { Vocabulary } from '@/types'

const { Title, Text } = Typography
const { Search } = Input

export function VocabularyPage() {
  const [loading, setLoading] = useState(false)
  const [vocabulary, setVocabulary] = useState<Vocabulary[]>([])
  const [total, setTotal] = useState(0)

  // 筛选条件
  const [grade, setGrade] = useState<string | undefined>()
  const [topic, setTopic] = useState<string | undefined>()
  const [page, setPage] = useState(1)
  const [size, setSize] = useState(20)

  // 搜索
  const [searchResult, setSearchResult] = useState<{
    word: string
    frequency: number
    occurrences: Array<{
      sentence: string
      passage_id: number
      source?: string
    }>
  } | null>(null)
  const [searchModalVisible, setSearchModalVisible] = useState(false)

  // 加载词汇列表
  useEffect(() => {
    loadVocabulary()
  }, [grade, topic, page, size])

  const loadVocabulary = async () => {
    setLoading(true)
    try {
      const response = await getVocabulary({
        grade,
        topic,
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
  }

  const handleSearch = async (value: string) => {
    if (!value.trim()) return

    setLoading(true)
    try {
      const result = await searchVocabulary(value.trim())
      setSearchResult(result)
      setSearchModalVisible(true)
    } catch (error) {
      message.error('搜索失败')
      console.error(error)
    } finally {
      setLoading(false)
    }
  }

  // 表格列定义
  const columns: ColumnsType<Vocabulary> = [
    {
      title: '单词',
      dataIndex: 'word',
      key: 'word',
      width: 150,
      render: (word: string) => <Text strong>{word}</Text>,
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
      title: '词频',
      dataIndex: 'frequency',
      key: 'frequency',
      width: 80,
      sorter: (a, b) => a.frequency - b.frequency,
      render: (freq: number) => <Tag color="blue">{freq}</Tag>,
    },
    {
      title: '例句',
      key: 'example',
      ellipsis: true,
      render: (_, record) => {
        const occ = record.occurrences[0]
        if (!occ) return '-'
        return (
          <Text type="secondary" italic>
            "{occ.sentence.slice(0, 80)}..."
          </Text>
        )
      },
    },
    {
      title: '出处',
      key: 'source',
      width: 200,
      render: (_, record) => {
        const occ = record.occurrences[0]
        if (!occ || !('source' in occ)) return '-'
        return (occ as any).source || '-'
      },
    },
  ]

  return (
    <div>
      <Title level={3}>高频词汇</Title>

      <Card style={{ marginBottom: 16 }}>
        <Space wrap>
          <Select
            placeholder="选择年级"
            allowClear
            style={{ width: 120 }}
            value={grade}
            onChange={setGrade}
            options={[
              { value: '初一', label: '初一' },
              { value: '初二', label: '初二' },
              { value: '初三', label: '初三' },
            ]}
          />
          <Select
            placeholder="选择话题"
            allowClear
            style={{ width: 200 }}
            value={topic}
            onChange={setTopic}
            options={[]}
          />
          <Search
            placeholder="搜索单词..."
            allowClear
            style={{ width: 300 }}
            onSearch={handleSearch}
            enterButton={<SearchOutlined />}
          />
        </Space>
      </Card>

      <Table
        columns={columns}
        dataSource={vocabulary}
        rowKey="id"
        loading={loading}
        pagination={{
          current: page,
          pageSize: size,
          total,
          showSizeChanger: true,
          showTotal: (total) => `共 ${total} 个`,
          onChange: (p, s) => {
            setPage(p)
            setSize(s)
          },
        }}
      />

      {/* 搜索结果弹窗 */}
      <Modal
        title={`"${searchResult?.word}" 搜索结果`}
        open={searchModalVisible}
        onCancel={() => setSearchModalVisible(false)}
        footer={null}
        width={800}
      >
        {searchResult && (
          <div>
            <Space style={{ marginBottom: 16 }}>
              <Text>词频：</Text>
              <Tag color="blue">{searchResult.frequency}</Tag>
            </Space>

            <Title level={5}>出现位置 ({searchResult.occurrences.length}处)</Title>

            {searchResult.occurrences.map((occ, index) => (
              <Card
                key={index}
                size="small"
                style={{ marginBottom: 8 }}
                extra={
                  <Button
                    type="link"
                    size="small"
                    icon={<EyeOutlined />}
                    onClick={() => {
                      // 跳转到文章详情页
                      window.open(`/reading/${occ.passage_id}`, '_blank')
                    }}
                  >
                    查看原文
                  </Button>
                }
              >
                <Text italic>"{occ.sentence}"</Text>
                {occ.source && (
                  <div style={{ marginTop: 8 }}>
                    <Text type="secondary">出处：{occ.source}</Text>
                  </div>
                )}
              </Card>
            ))}
          </div>
        )}
      </Modal>
    </div>
  )
}
