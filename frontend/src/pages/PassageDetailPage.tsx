/**
 * 文章详情页（含定位功能）
 *
 * 核心功能：
 * - 左侧显示原文
 * - 右侧显示词汇列表
 * - 点击词汇可定位到原文并高亮
 */
import { useState, useEffect, useRef, useCallback } from 'react'
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
  Descriptions,
  Tabs,
} from 'antd'
import { ArrowLeftOutlined, CheckCircleOutlined, EyeOutlined, EyeInvisibleOutlined } from '@ant-design/icons'

import { getPassage } from '@/services/readingService'
import type { PassageDetail, VocabularyInPassage, VocabularyOccurrence, Question } from '@/types'

const { Title, Text, Paragraph } = Typography

export function PassageDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const contentRef = useRef<HTMLDivElement>(null)

  const [loading, setLoading] = useState(true)
  const [passage, setPassage] = useState<PassageDetail | null>(null)

  // 当前高亮的词汇
  const [highlightedWord, setHighlightedWord] = useState<string | null>(null)
  // 当前高亮位置
  const [highlightPositions, setHighlightPositions] = useState<VocabularyOccurrence[]>([])
  // 当前显示的第几个位置
  const [currentIndex, setCurrentIndex] = useState(0)

  // 加载文章详情
  useEffect(() => {
    if (id) {
      loadPassage(parseInt(id))
    }
  }, [id])

  const loadPassage = async (passageId: number) => {
    setLoading(true)
    try {
      const data = await getPassage(passageId)
      setPassage(data)
    } catch (error) {
      message.error('加载文章失败')
      console.error(error)
    } finally {
      setLoading(false)
    }
  }

  // 点击词汇，定位到原文
  const handleWordClick = useCallback(
    (word: VocabularyInPassage) => {
      setHighlightedWord(word.word)
      setHighlightPositions(word.occurrences)
      setCurrentIndex(0)

      // 滚动到第一个位置
      if (word.occurrences.length > 0) {
        scrollToPosition(word.occurrences[0].char_position)
      }
    },
    []
  )

  // 切换到下一个位置
  const handleNextOccurrence = useCallback(() => {
    if (highlightPositions.length === 0) return

    const nextIndex = (currentIndex + 1) % highlightPositions.length
    setCurrentIndex(nextIndex)
    scrollToPosition(highlightPositions[nextIndex].char_position)
  }, [currentIndex, highlightPositions])

  // 滚动到指定位置
  const scrollToPosition = useCallback((charPosition: number) => {
    if (!contentRef.current) return

    // 查找包含该位置的文本节点
    const walker = document.createTreeWalker(
      contentRef.current,
      NodeFilter.SHOW_TEXT,
      null
    )

    let currentPos = 0
    let node: Node | null
    while ((node = walker.nextNode())) {
      const nodeLength = node.textContent?.length || 0
      if (currentPos + nodeLength > charPosition) {
        // 找到包含目标位置的节点
        const element = node.parentElement
        if (element) {
          element.scrollIntoView({ behavior: 'smooth', block: 'center' })
        }
        break
      }
      currentPos += nodeLength
    }
  }, [])

  // 渲染带高亮的内容
  const renderHighlightedContent = useCallback(() => {
    if (!passage?.content) return null

    if (!highlightedWord || highlightPositions.length === 0) {
      return passage.content
    }

    // 获取当前位置
    const current = highlightPositions[currentIndex]
    if (!current) return passage.content

    // 构建高亮内容
    const before = passage.content.slice(0, current.char_position)
    const highlight = passage.content.slice(
      current.char_position,
      current.end_position || current.char_position + highlightedWord.length
    )
    const after = passage.content.slice(current.end_position || current.char_position + highlightedWord.length)

    return (
      <>
        {before}
        <mark className="highlight">{highlight}</mark>
        {after}
      </>
    )
  }, [passage?.content, highlightedWord, highlightPositions, currentIndex])

  // 清除高亮
  const handleClearHighlight = useCallback(() => {
    setHighlightedWord(null)
    setHighlightPositions([])
    setCurrentIndex(0)
  }, [])

  // 返回列表
  const handleBack = () => {
    navigate('/reading')
  }

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '100px 0' }}>
        <Spin size="large" />
      </div>
    )
  }

  if (!passage) {
    return <Empty description="文章不存在" />
  }

  // 出处信息
  const source = passage.source

  return (
    <div>
      {/* 顶部信息和操作栏 */}
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={handleBack}>
          返回列表
        </Button>
        <Title level={4} style={{ margin: 0 }}>
          {passage.passage_type}篇 - {passage.primary_topic || '未分类'}
        </Title>
        {passage.topic_verified && (
          <Tag icon={<CheckCircleOutlined />} color="success">
            已校对
          </Tag>
        )}
      </Space>

      {/* 出处信息 */}
      <Card size="small" style={{ marginBottom: 16 }}>
        <Descriptions size="small" column={6}>
          <Descriptions.Item label="年份">{source?.year || '-'}</Descriptions.Item>
          <Descriptions.Item label="区县">{source?.region || '-'}</Descriptions.Item>
          <Descriptions.Item label="年级">{source?.grade || '-'}</Descriptions.Item>
          <Descriptions.Item label="类型">{source?.exam_type || '-'}</Descriptions.Item>
          <Descriptions.Item label="词数">{passage.word_count || '-'}</Descriptions.Item>
          <Descriptions.Item label="置信度">
            {passage.topic_confidence ? `${(passage.topic_confidence * 100).toFixed(0)}%` : '-'}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      {/* 主内容区：左右分栏 */}
      <div style={{ display: 'flex', gap: 16, height: 'calc(100vh - 280px)' }}>
        {/* 左侧：原文区 */}
        <Card
          title="原文内容"
          style={{ flex: 2, overflow: 'hidden' }}
          extra={
            highlightedWord && (
              <Space>
                <Text type="secondary">
                  "{highlightedWord}" - 第 {currentIndex + 1}/{highlightPositions.length} 处
                </Text>
                <Button size="small" onClick={handleNextOccurrence}>
                  下一处
                </Button>
                <Button size="small" onClick={handleClearHighlight}>
                  清除
                </Button>
              </Space>
            )
          }
        >
          <div
            ref={contentRef}
            className="passage-content"
            style={{
              height: 'calc(100% - 20px)',
              overflowY: 'auto',
              padding: '8px 0',
            }}
          >
            {renderHighlightedContent()}
          </div>
        </Card>

        {/* 右侧：词汇和题目 */}
        <Card
          style={{ flex: 1, overflow: 'hidden' }}
          bodyStyle={{ padding: 0 }}
        >
          <Tabs
            defaultActiveKey="vocabulary"
            style={{ height: '100%' }}
            className="right-tabs"
            items={[
              {
                key: 'vocabulary',
                label: `高频词汇 (${passage.vocabulary?.length || 0})`,
                children: (
                  <div style={{ height: 'calc(100vh - 400px)', overflowY: 'auto', padding: '0 16px' }}>
                    {passage.vocabulary && passage.vocabulary.length > 0 ? (
                      <List
                        dataSource={passage.vocabulary}
                        renderItem={(item) => (
                          <List.Item
                            className={`vocab-item ${highlightedWord === item.word ? 'active' : ''}`}
                            onClick={() => handleWordClick(item)}
                            style={{ cursor: 'pointer' }}
                          >
                            <div style={{ width: '100%' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                                <Text strong style={{ fontSize: 16 }}>{item.word}</Text>
                                <Tag color="blue">{item.frequency}次</Tag>
                              </div>
                              {item.definition && (
                                <Text type="secondary" style={{ fontSize: 13 }}>
                                  {item.definition}
                                </Text>
                              )}
                              {item.occurrences[0] && (
                                <div
                                  style={{
                                    marginTop: 8,
                                    paddingLeft: 8,
                                    borderLeft: '2px solid #d9d9d9',
                                  }}
                                >
                                  <Text
                                    type="secondary"
                                    italic
                                    style={{ fontSize: 12 }}
                                  >
                                    "{item.occurrences[0].sentence.slice(0, 60)}..."
                                  </Text>
                                </div>
                              )}
                            </div>
                          </List.Item>
                        )}
                      />
                    ) : (
                      <Empty description="暂无词汇数据" />
                    )}
                  </div>
                ),
              },
              {
                key: 'questions',
                label: `题目 (${passage.questions?.length || 0})`,
                children: (
                  <div style={{ height: 'calc(100vh - 400px)', overflowY: 'auto', padding: '0 16px' }}>
                    {passage.questions && passage.questions.length > 0 ? (
                      <Space direction="vertical" style={{ width: '100%' }} size="middle">
                        {passage.questions.map((q, idx) => (
                          <QuestionCard key={q.id || idx} question={q} />
                        ))}
                      </Space>
                    ) : (
                      <Empty description="暂无题目数据" />
                    )}
                  </div>
                ),
              },
            ]}
          />
        </Card>
      </div>
    </div>
  )
}

// 题目卡片组件
function QuestionCard({ question }: { question: Question }) {
  const [showAnswer, setShowAnswer] = useState(false)

  return (
    <Card
      size="small"
      title={
        <Space>
          <Tag color="blue">Q{question.question_number}</Tag>
          <Text style={{ fontSize: 14 }}>{question.question_text}</Text>
        </Space>
      }
    >
      <Space direction="vertical" style={{ width: '100%' }}>
        {question.options && (
          <div>
            {['A', 'B', 'C', 'D'].map((opt) => (
              <div key={opt} style={{ marginBottom: 4, paddingLeft: 8 }}>
                <Text>
                  <Text strong>{opt}.</Text> {question.options?.[opt as keyof typeof question.options] || '-'}
                </Text>
              </div>
            ))}
          </div>
        )}

        <Button
          type="link"
          icon={showAnswer ? <EyeInvisibleOutlined /> : <EyeOutlined />}
          onClick={() => setShowAnswer(!showAnswer)}
          style={{ padding: 0 }}
        >
          {showAnswer ? '隐藏答案' : '显示答案'}
        </Button>

        {showAnswer && (
          <div style={{
            padding: 8,
            background: '#f6ffed',
            borderLeft: '3px solid #52c41a',
            borderRadius: 4
          }}>
            <Space direction="vertical" style={{ width: '100%' }}>
              <Text>
                <Text strong type="success">正确答案：</Text>
                <Tag color="success">{question.correct_answer}</Tag>
              </Text>
              {question.answer_explanation && (
                <div>
                  <Text strong type="secondary">解析：</Text>
                  <Paragraph style={{ margin: '4px 0', whiteSpace: 'pre-wrap' }}>
                    {question.answer_explanation}
                  </Paragraph>
                </div>
              )}
            </Space>
          </div>
        )}
      </Space>
    </Card>
  )
}
