/**
 * 讲义主题列表组件
 *
 * [INPUT]: 依赖 antd、readingService
 * [OUTPUT]: 对外提供 TopicList 组件
 * [POS]: frontend/src/components/handout 的主题列表
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */
import { useState, useEffect } from 'react'
import { List, Card, Tag, Button, Typography, Space, Spin, Empty } from 'antd'
import { ArrowLeftOutlined, BookOutlined } from '@ant-design/icons'

import { getTopicStatsForGrade } from '@/services/readingService'
import type { TopicStats } from '@/types'

const { Title, Text } = Typography

interface TopicListProps {
  grade: string
  onSelect: (topic: string) => void
  onBack: () => void
}

export function TopicList({ grade, onSelect, onBack }: TopicListProps) {
  const [topics, setTopics] = useState<TopicStats[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadTopics()
  }, [grade])

  const loadTopics = async () => {
    try {
      setLoading(true)
      const response = await getTopicStatsForGrade(grade)
      setTopics(response.topics)
    } catch (error) {
      console.error('加载主题失败:', error)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 48 }}>
        <Spin size="large" />
        <div style={{ marginTop: 16 }}>
          <Text type="secondary">加载主题列表...</Text>
        </div>
      </div>
    )
  }

  if (topics.length === 0) {
    return (
      <div>
        <Space style={{ marginBottom: 16 }}>
          <Button icon={<ArrowLeftOutlined />} onClick={onBack}>
            返回年级选择
          </Button>
        </Space>
        <Empty description="该年级暂无主题数据" />
      </div>
    )
  }

  return (
    <div>
      <Space style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }}>
        <Button icon={<ArrowLeftOutlined />} onClick={onBack}>
          返回年级选择
        </Button>
        <Title level={3} style={{ margin: 0 }}>
          {grade}阅读 CD篇 - 主题列表
        </Title>
        <div style={{ width: 120 }} /> {/* 占位符，保持居中 */}
      </Space>

      <List
        grid={{
          gutter: 16,
          xs: 1,
          sm: 2,
          md: 3,
          lg: 3,
          xl: 4,
          xxl: 4,
        }}
        dataSource={topics}
        renderItem={(item) => (
          <List.Item>
            <Card
              hoverable
              onClick={() => onSelect(item.topic)}
              style={{
                cursor: 'pointer',
                transition: 'all 0.3s',
              }}
              styles={{
                body: {
                  padding: '20px',
                },
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.transform = 'translateY(-4px)'
                e.currentTarget.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.15)'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = 'translateY(0)'
                e.currentTarget.style.boxShadow = 'none'
              }}
            >
              <Title level={4} style={{ marginBottom: 12 }}>
                <BookOutlined style={{ marginRight: 8 }} />
                {item.topic}
              </Title>

              <Space wrap size={[8, 16]}>
                <Tag color="blue" style={{ fontSize: 14, padding: '4px 12px' }}>
                  {item.passage_count} 篇文章
                </Tag>
                {item.recent_years.map(year => (
                  <Tag key={year} style={{ fontSize: 14, padding: '4px 8px' }}>
                    {year}
                  </Tag>
                ))}
              </Space>
            </Card>
          </List.Item>
        )}
      />
    </div>
  )
}
