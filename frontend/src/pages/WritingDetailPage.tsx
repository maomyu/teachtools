/**
 * 作文详情页
 *
 * [INPUT]: 依赖 antd 组件、@/services/writingService、@/types
 * [OUTPUT]: 对外提供 WritingDetailPage 组件
 * [POS]: frontend/src/pages 的作文详情页面
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */
import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Card,
  Descriptions,
  Tag,
  Button,
  Space,
  Typography,
  message,
  Tabs,
  Spin,
  Empty,
  Divider,
  Tooltip,
  Popconfirm,
  Row,
  Col,
  List,
  Alert,
  Collapse,
} from 'antd'
import {
  ArrowLeftOutlined,
  FileTextOutlined,
  FilePdfOutlined,
  BulbOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  CopyOutlined,
  ThunderboltOutlined,
  BookOutlined,
  RiseOutlined,
  DeleteOutlined,
  TranslationOutlined,
} from '@ant-design/icons'

import {
  getWritingDetail,
  generateSample,
  deleteSample,
} from '@/services/writingService'
import type { WritingTaskDetail, WritingTemplate, WritingSample } from '@/types'

const { Title, Paragraph, Text } = Typography

export function WritingDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [loading, setLoading] = useState(false)
  const [detail, setDetail] = useState<WritingTaskDetail | null>(null)
  const [generating, setGenerating] = useState(false)
  const [activeTab, setActiveTab] = useState('task')

  // 加载详情
  useEffect(() => {
    if (id) {
      loadDetail()
    }
  }, [id])

  const loadDetail = async () => {
    if (!id) return
    setLoading(true)
    try {
      const response = await getWritingDetail(parseInt(id))
      setDetail(response)
    } catch (error) {
      message.error('加载作文详情失败')
      console.error(error)
    } finally {
      setLoading(false)
    }
  }

  // 生成范文
  const handleGenerateSample = async () => {
    if (!id) return
    setGenerating(true)
    try {
      await generateSample(parseInt(id))
      message.success('范文生成成功')
      loadDetail()
    } catch (error) {
      message.error('范文生成失败')
      console.error(error)
    } finally {
      setGenerating(false)
    }
  }

  // 删除范文
  const handleDeleteSample = async (sampleId: number) => {
    if (!id) return
    try {
      await deleteSample(parseInt(id), sampleId)
      message.success('范文已删除')
      loadDetail()
    } catch (error) {
      message.error('删除范文失败')
      console.error(error)
    }
  }

  // 导出 PDF（待实现）
  const handleExportPdf = () => {
    message.info('PDF 导出功能开发中...')
  }

  // 文体类型颜色
  const getGroupColor = (type?: string) => {
    switch (type) {
      case '应用文':
        return 'blue'
      case '记叙文':
        return 'green'
      case '表达拓展类':
        return 'gold'
      default:
        return 'default'
    }
  }

  // 渲染题目内容
  const renderTaskContent = () => {
    if (!detail) return null

    return (
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        {/* 基本信息 */}
        <Card>
          <Descriptions column={3} bordered size="small">
            <Descriptions.Item label="年级">
              <Tag color="blue">{detail.grade || '未设置'}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="学期">
              <Tag color="cyan">{detail.semester || '未设置'}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="考试类型">
              <Tag color="purple">{detail.exam_type || '未设置'}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="文体组">
              {detail.group_category ? (
                <Space>
                  <Tag color={getGroupColor(detail.group_category.name)}>
                    {detail.group_category.name}
                  </Tag>
                </Space>
              ) : (
                <Tag>未识别</Tag>
              )}
            </Descriptions.Item>
            <Descriptions.Item label="主类">
              {detail.major_category?.name || '未分类'}
            </Descriptions.Item>
            <Descriptions.Item label="子类">
              {detail.category?.name || '未分类'}
            </Descriptions.Item>
            <Descriptions.Item label="训练词数">
              {detail.training_word_target || '150词左右'}
            </Descriptions.Item>
          </Descriptions>
        </Card>

        {/* 题目内容 */}
        <Card title={<><FileTextOutlined /> 题目内容</>}>
          <Paragraph style={{ whiteSpace: 'pre-wrap', fontSize: 16 }}>
            {detail.task_content}
          </Paragraph>
          {detail.requirements && (
            <>
              <Divider />
              <Title level={5}>写作要求</Title>
              <Paragraph style={{ whiteSpace: 'pre-wrap' }}>
                {detail.requirements}
              </Paragraph>
            </>
          )}
        </Card>

        {/* 操作区 */}
        <Card>
          <Space wrap>
            <Button
              type="primary"
              icon={<FileTextOutlined />}
              loading={generating}
              onClick={handleGenerateSample}
            >
              生成范文
            </Button>
            <Button
              icon={<FilePdfOutlined />}
              onClick={handleExportPdf}
              disabled={!detail.templates?.length && !detail.samples?.length}
            >
              导出讲义 PDF
            </Button>
            <Popconfirm
              title="确定删除这篇作文吗？"
              onConfirm={() => navigate('/writing')}
              okText="确定"
              cancelText="取消"
            >
              <Button danger>删除作文</Button>
            </Popconfirm>
          </Space>
        </Card>
      </Space>
    )
  }

  // 渲染模板（增强版 - 包含句型库、词汇表等）
  const renderTemplates = () => {
    if (!detail?.templates?.length) {
      return (
        <Empty
          description="暂无模板"
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        >
          <Button type="primary" onClick={handleGenerateSample}>
            生成模板和范文
          </Button>
        </Empty>
      )
    }

    // 解析 JSON 字段的辅助函数
    const parseJsonField = (field: string | undefined): any[] => {
      if (!field) return []
      try {
        return JSON.parse(field)
      } catch {
        return []
      }
    }

    // 复制到剪贴板
    const copyToClipboard = (text: string) => {
      navigator.clipboard.writeText(text)
      message.success('已复制到剪贴板')
    }

    return (
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        {detail.templates.map((template: WritingTemplate) => {
          const openingSentences = parseJsonField(template.opening_sentences)
          const closingSentences = parseJsonField(template.closing_sentences)
          const transitionWords = parseJsonField(template.transition_words)
          const advancedVocabulary = parseJsonField(template.advanced_vocabulary)
          const grammarPoints = parseJsonField(template.grammar_points)

          return (
            <Space direction="vertical" size="middle" style={{ width: '100%' }} key={template.id}>
              {/* 文章结构 */}
              {template.structure && (
                <Card title={<><BulbOutlined /> 文章结构</>} size="small">
                  <Paragraph style={{ whiteSpace: 'pre-wrap', margin: 0 }}>
                    {template.structure}
                  </Paragraph>
                </Card>
              )}

              {/* 模板内容 */}
              <Card title={<><FileTextOutlined /> 模板内容</>} size="small">
                <Paragraph
                  style={{
                    whiteSpace: 'pre-wrap',
                    backgroundColor: '#f5f5f5',
                    padding: 16,
                    borderRadius: 8,
                    margin: 0,
                  }}
                >
                  {template.template_content}
                </Paragraph>
              </Card>

              {/* 句型库 - 开头和结尾 */}
              {(openingSentences.length > 0 || closingSentences.length > 0) && (
                <Row gutter={16}>
                  {openingSentences.length > 0 && (
                    <Col span={12}>
                      <Card
                        title={<><ThunderboltOutlined /> 开头句型</>}
                        size="small"
                        extra={<Tag color="blue">{openingSentences.length}句</Tag>}
                      >
                        <List
                          size="small"
                          dataSource={openingSentences}
                          renderItem={(item: string) => (
                            <List.Item
                              actions={[
                                <Tooltip title="复制" key="copy">
                                  <Button
                                    type="text"
                                    size="small"
                                    icon={<CopyOutlined />}
                                    onClick={() => copyToClipboard(item)}
                                  />
                                </Tooltip>
                              ]}
                            >
                              <Text>{item}</Text>
                            </List.Item>
                          )}
                        />
                      </Card>
                    </Col>
                  )}
                  {closingSentences.length > 0 && (
                    <Col span={12}>
                      <Card
                        title={<><CheckCircleOutlined /> 结尾句型</>}
                        size="small"
                        extra={<Tag color="green">{closingSentences.length}句</Tag>}
                      >
                        <List
                          size="small"
                          dataSource={closingSentences}
                          renderItem={(item: string) => (
                            <List.Item
                              actions={[
                                <Tooltip title="复制" key="copy">
                                  <Button
                                    type="text"
                                    size="small"
                                    icon={<CopyOutlined />}
                                    onClick={() => copyToClipboard(item)}
                                  />
                                </Tooltip>
                              ]}
                            >
                              <Text>{item}</Text>
                            </List.Item>
                          )}
                        />
                      </Card>
                    </Col>
                  )}
                </Row>
              )}

              {/* 过渡词汇 */}
              {transitionWords.length > 0 && (
                <Card title={<><RiseOutlined /> 过渡词汇</>} size="small">
                  <Space wrap>
                    {transitionWords.map((item: string, idx: number) => (
                      <Tag key={idx} color="purple" style={{ margin: 4 }}>
                        {item}
                      </Tag>
                    ))}
                  </Space>
                </Card>
              )}

              {/* 高级词汇替换 */}
              {advancedVocabulary.length > 0 && (
                <Card title={<><BookOutlined /> 高级词汇替换</>} size="small">
                  <Space wrap>
                    {advancedVocabulary.map((item: { word: string; basic: string }, idx: number) => (
                      <Tag key={idx} color="orange" style={{ margin: 4 }}>
                        {item.basic} → {item.word}
                      </Tag>
                    ))}
                  </Space>
                </Card>
              )}

              {/* 语法要点 */}
              {grammarPoints.length > 0 && (
                <Card title="语法要点" size="small">
                  <List
                    size="small"
                    dataSource={grammarPoints}
                    renderItem={(item: string) => (
                      <List.Item>
                        <Text>• {item}</Text>
                      </List.Item>
                    )}
                  />
                </Card>
              )}

              {/* 写作技巧 */}
              {template.tips && (
                <Alert
                  type="info"
                  message="写作技巧"
                  description={
                    <div style={{ whiteSpace: 'pre-wrap' }}>{template.tips}</div>
                  }
                />
              )}
            </Space>
          )
        })}
      </Space>
    )
  }

  // 渲染范文
  const renderSamples = () => {
    if (!detail?.samples?.length) {
      return (
        <Empty
          description="暂无范文"
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        >
          <Button type="primary" onClick={handleGenerateSample}>
            生成范文
          </Button>
        </Empty>
      )
    }

    return (
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        {detail.samples.map((sample: WritingSample, index: number) => (
          <Card
            key={sample.id}
            title={
              <Space>
                <FileTextOutlined />
                范文 {index + 1}
                {sample.word_count && (
                  <Tag color="blue">{sample.word_count} 词</Tag>
                )}
              </Space>
            }
            extra={
              <Space>
                {sample.score_level && (
                  <Tag color="gold">{sample.score_level}</Tag>
                )}
                <Tag>{sample.sample_type}</Tag>
                <Popconfirm
                  title="确定删除这篇范文吗？"
                  description="删除后无法恢复"
                  onConfirm={() => handleDeleteSample(sample.id)}
                  okText="确定"
                  cancelText="取消"
                >
                  <Button
                    type="text"
                    danger
                    icon={<DeleteOutlined />}
                    size="small"
                  />
                </Popconfirm>
              </Space>
            }
          >
            <Paragraph
              style={{
                whiteSpace: 'pre-wrap',
                fontSize: 15,
                lineHeight: 1.8,
              }}
            >
              {sample.sample_content}
            </Paragraph>

            {/* 中文翻译（可折叠） */}
            {sample.translation && (
              <Collapse
                style={{ marginTop: 16 }}
                items={[
                  {
                    key: 'translation',
                    label: (
                      <Space>
                        <TranslationOutlined />
                        <span>中文翻译</span>
                      </Space>
                    ),
                    children: (
                      <Paragraph
                        style={{
                          whiteSpace: 'pre-wrap',
                          fontSize: 14,
                          lineHeight: 2,
                          margin: 0,
                          color: '#666',
                        }}
                      >
                        {sample.translation}
                      </Paragraph>
                    ),
                  },
                ]}
              />
            )}

            <Divider />
            <Space split={<Divider type="vertical" />}>
              <Text type="secondary">
                <ClockCircleOutlined /> {new Date(sample.created_at).toLocaleString()}
              </Text>
            </Space>
          </Card>
        ))}
      </Space>
    )
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 400 }}>
        <Spin size="large" tip="加载中..." />
      </div>
    )
  }

  if (!detail) {
    return (
      <div style={{ padding: 24 }}>
        <Empty description="作文不存在" />
        <Button onClick={() => navigate('/writing')}>返回列表</Button>
      </div>
    )
  }

  const tabItems = [
    {
      key: 'task',
      label: '题目详情',
      children: renderTaskContent(),
    },
    {
      key: 'template',
      label: (
        <Space>
          <BulbOutlined />
          模板
          {detail.templates?.length > 0 && (
            <Tag color="blue">{detail.templates.length}</Tag>
          )}
        </Space>
      ),
      children: renderTemplates(),
    },
    {
      key: 'sample',
      label: (
        <Space>
          <FileTextOutlined />
          范文
          {detail.samples?.length > 0 && (
            <Tag color="green">{detail.samples.length}</Tag>
          )}
        </Space>
      ),
      children: renderSamples(),
    },
  ]

  return (
    <div style={{ padding: 24 }}>
      {/* 顶部导航 */}
      <div style={{ marginBottom: 16 }}>
        <Button
          type="text"
          icon={<ArrowLeftOutlined />}
          onClick={() => navigate('/writing')}
        >
          返回列表
        </Button>
      </div>

      {/* 标题区 */}
      <Card style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Title level={3} style={{ margin: 0 }}>
            {detail.source?.grade || ''} {detail.source?.exam_type || ''} 作文
            {detail.category?.name && (
              <Text type="secondary" style={{ marginLeft: 12, fontSize: 14 }}>
                · {detail.category.name}
              </Text>
            )}
          </Title>
          {detail.group_category && (
            <Tag color={getGroupColor(detail.group_category.name)} style={{ fontSize: 14 }}>
              {detail.group_category.name}
            </Tag>
          )}
        </div>
      </Card>

      {/* 内容区 */}
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={tabItems}
        size="large"
      />
    </div>
  )
}
