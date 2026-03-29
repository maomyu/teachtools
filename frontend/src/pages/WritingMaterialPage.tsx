/**
 * 作文素材库页面
 *
 * [INPUT]: 依赖 antd 组件、@/services/writingService、@/types
 * [OUTPUT]: 对外提供 WritingMaterialPage 组件
 * [POS]: frontend/src/pages 的作文素材库页面
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */
import { useState, useEffect } from 'react'
import {
  Card,
  Select,
  Tag,
  Typography,
  Space,
  Empty,
  Spin,
  Row,
  Col,
  Divider,
} from 'antd'
import {
  BookOutlined,
  BulbOutlined,
  FormatPainterOutlined,
  HighlightOutlined,
} from '@ant-design/icons'

import { getWritingFilters } from '@/services/writingService'

const { Title, Paragraph, Text } = Typography

// 话题素材数据（静态数据，后续可从后端获取）
const TOPIC_MATERIALS: Record<string, {
  keywords: string[]
  sentencePatterns: string[]
  tips: string[]
}> = {
  '校园生活': {
    keywords: ['school life', 'campus', 'classmate', 'teacher', 'homework', 'exam', 'subject'],
    sentencePatterns: [
      'I enjoy my school life because...',
      'My favorite subject is... because...',
      'I have learned a lot from...',
      'It is important for students to...',
    ],
    tips: [
      '使用第一人称叙述，增强真实感',
      '描述具体事件而非泛泛而谈',
      '加入对话使文章更生动',
    ],
  },
  '家庭亲情': {
    keywords: ['family', 'parent', 'mother', 'father', 'love', 'care', 'support', 'home'],
    sentencePatterns: [
      'My family is very important to me because...',
      'I am grateful for my parents who...',
      'There are... people in my family.',
      'We always... together on weekends.',
    ],
    tips: [
      '通过具体事例展现亲情',
      '使用细节描写增加感染力',
      '结尾升华主题，表达感恩',
    ],
  },
  '环境保护': {
    keywords: ['environment', 'protect', 'pollution', 'save', 'earth', 'green', 'recycle', 'waste'],
    sentencePatterns: [
      'It is our duty to protect the environment.',
      'We should... to save our planet.',
      'If everyone... the world would be better.',
      'I suggest that we...',
    ],
    tips: [
      '提出具体可行的环保建议',
      '使用数据或事实增强说服力',
      '呼吁读者共同行动',
    ],
  },
  '健康生活': {
    keywords: ['health', 'exercise', 'sport', 'diet', 'vegetable', 'fruit', 'sleep', 'habit'],
    sentencePatterns: [
      'Keeping healthy is very important.',
      'To stay healthy, we should...',
      'I exercise... times a week.',
      'A healthy lifestyle includes...',
    ],
    tips: [
      '从饮食、运动、作息多角度论述',
      '给出具体建议而非空泛说教',
      '可以结合个人经历',
    ],
  },
  '传统文化': {
    keywords: ['tradition', 'culture', 'festival', 'custom', 'celebrate', 'history', 'Chinese'],
    sentencePatterns: [
      '... is one of the most important traditional festivals in China.',
      'People usually... during this festival.',
      'It has a history of... years.',
      'The festival represents...',
    ],
    tips: [
      '介绍节日的起源和习俗',
      '描述具体的庆祝活动',
      '表达对传统文化的热爱',
    ],
  },
  '科技与未来': {
    keywords: ['technology', 'Internet', 'computer', 'smartphone', 'future', 'develop', 'AI'],
    sentencePatterns: [
      'With the development of technology...',
      'Technology has changed our lives in many ways.',
      'In the future, I believe...',
      'We should make good use of...',
    ],
    tips: [
      '辩证看待科技的利弊',
      '结合具体例子说明',
      '展望未来要有合理依据',
    ],
  },
}

// 应用文写作模板
const APPLICATION_TEMPLATES = {
  '书信': {
    opening: ['Dear...', 'I am writing to...', 'Thank you for your letter.'],
    closing: ['Looking forward to your reply.', 'Best wishes!', 'Yours sincerely,'],
    tips: ['开头表明写信目的', '正文分段清晰', '结尾表达期望'],
  },
  '通知': {
    opening: ['NOTICE', 'Attention please!', 'All students are informed that...'],
    closing: ['Please be on time.', 'Everyone is welcome.', 'Thank you for your attention.'],
    tips: ['格式规范，标题居中', '时间地点要明确', '语言简洁正式'],
  },
  '邀请': {
    opening: ['I would like to invite you to...', 'You are cordially invited to...'],
    closing: ['We would be honored by your presence.', 'Please let us know if you can come.'],
    tips: ['清楚说明活动信息', '表达诚挚邀请', '提供回复方式'],
  },
  '日记': {
    opening: ['Today was a special day.', 'Date:... Weather:...'],
    closing: ['What a meaningful day!', 'I will never forget today.'],
    tips: ['记录真实感受', '时间顺序清晰', '可以包含心理描写'],
  },
}

export function WritingMaterialPage() {
  const [loading, setLoading] = useState(false)
  const [topics, setTopics] = useState<string[]>([])
  const [selectedTopic, setSelectedTopic] = useState<string | undefined>()

  useEffect(() => {
    loadFilters()
  }, [])

  const loadFilters = async () => {
    setLoading(true)
    try {
      const response = await getWritingFilters()
      const dynamicTopics = response.categories.map((item) => item.name)
      const allTopics = [...new Set([...Object.keys(TOPIC_MATERIALS), ...dynamicTopics])]
      setTopics(allTopics)
    } catch (error) {
      // 使用静态话题作为备用
      setTopics(Object.keys(TOPIC_MATERIALS))
    } finally {
      setLoading(false)
    }
  }

  // 获取当前选中话题的素材
  const currentMaterial = selectedTopic ? TOPIC_MATERIALS[selectedTopic] : null

  return (
    <div style={{ padding: 24 }}>
      <Card>
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          {/* 标题 */}
          <div>
            <Title level={3} style={{ margin: 0 }}>
              <BookOutlined style={{ marginRight: 8 }} />
              作文素材库
            </Title>
            <Text type="secondary">
              按话题分类的写作素材，包括关键词、句型和写作技巧
            </Text>
          </div>

          {/* 话题选择器 */}
          <Select
            allowClear
            showSearch
            placeholder="选择话题查看素材"
            style={{ width: 300 }}
            value={selectedTopic}
            onChange={setSelectedTopic}
            options={topics.map((t) => ({ value: t, label: t }))}
            filterOption={(input, option) =>
              (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
            }
          />

          <Divider />

          {loading ? (
            <div style={{ textAlign: 'center', padding: 40 }}>
              <Spin size="large" />
            </div>
          ) : selectedTopic && currentMaterial ? (
            <Row gutter={[16, 16]}>
              {/* 关键词卡片 */}
              <Col xs={24} md={12}>
                <Card
                  title={
                    <>
                      <HighlightOutlined style={{ marginRight: 8 }} />
                      高频词汇
                    </>
                  }
                  size="small"
                >
                  <Space wrap>
                    {currentMaterial.keywords.map((word) => (
                      <Tag key={word} color="blue">
                        {word}
                      </Tag>
                    ))}
                  </Space>
                </Card>
              </Col>

              {/* 写作技巧卡片 */}
              <Col xs={24} md={12}>
                <Card
                  title={
                    <>
                      <BulbOutlined style={{ marginRight: 8 }} />
                      写作技巧
                    </>
                  }
                  size="small"
                >
                  <ul style={{ margin: 0, paddingLeft: 20 }}>
                    {currentMaterial.tips.map((tip, index) => (
                      <li key={index}>
                        <Text>{tip}</Text>
                      </li>
                    ))}
                  </ul>
                </Card>
              </Col>

              {/* 常用句型卡片 */}
              <Col xs={24}>
                <Card
                  title={
                    <>
                      <FormatPainterOutlined style={{ marginRight: 8 }} />
                      常用句型
                    </>
                  }
                  size="small"
                >
                  <Space direction="vertical" style={{ width: '100%' }}>
                    {currentMaterial.sentencePatterns.map((pattern, index) => (
                      <Paragraph
                        key={index}
                        style={{
                          margin: 0,
                          padding: '8px 12px',
                          backgroundColor: '#f5f5f5',
                          borderRadius: 4,
                        }}
                      >
                        {pattern}
                      </Paragraph>
                    ))}
                  </Space>
                </Card>
              </Col>
            </Row>
          ) : (
            <Empty description="请选择话题查看素材" />
          )}

          <Divider />

          {/* 应用文模板 */}
          <div>
            <Title level={4}>
              <BookOutlined style={{ marginRight: 8 }} />
              应用文写作模板
            </Title>
            <Row gutter={[16, 16]}>
              {Object.entries(APPLICATION_TEMPLATES).map(([type, template]) => (
                <Col xs={24} md={12} lg={6} key={type}>
                  <Card title={type} size="small">
                    <Space direction="vertical" size="small" style={{ width: '100%' }}>
                      <div>
                        <Text strong>开头：</Text>
                        <br />
                        {template.opening.map((o, i) => (
                          <Text key={i} type="secondary">
                            {o}
                            <br />
                          </Text>
                        ))}
                      </div>
                      <div>
                        <Text strong>结尾：</Text>
                        <br />
                        {template.closing.map((c, i) => (
                          <Text key={i} type="secondary">
                            {c}
                            <br />
                          </Text>
                        ))}
                      </div>
                      <Divider style={{ margin: '8px 0' }} />
                      <div>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          {template.tips.join(' | ')}
                        </Text>
                      </div>
                    </Space>
                  </Card>
                </Col>
              ))}
            </Row>
          </div>
        </Space>
      </Card>
    </div>
  )
}
