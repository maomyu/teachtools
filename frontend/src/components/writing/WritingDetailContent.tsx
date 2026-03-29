/**
 * 作文详情内容组件（抽屉内使用）
 *
 * [INPUT]: 依赖 antd 组件、@/services/writingService、@/types
 * [OUTPUT]: 对外提供 WritingDetailContent 组件
 * [POS]: frontend/src/components/writing 的作文详情内容组件
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */
import { useState, useEffect } from 'react'
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
  Progress,
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
  CloseOutlined,
} from '@ant-design/icons'

import {
  getWritingDetail,
  generateSample,
  deleteSample,
} from '@/services/writingService'
import type { WritingTaskDetail, WritingTemplate, WritingSample } from '@/types'

const { Title, Paragraph, Text } = Typography

interface WritingDetailContentProps {
  writingId: number
  onClose: () => void
}

export function WritingDetailContent({ writingId, onClose }: WritingDetailContentProps) {
  const [loading, setLoading] = useState(true)
  const [detail, setDetail] = useState<WritingTaskDetail | null>(null)
  const [generating, setGenerating] = useState(false)
  const [activeTab, setActiveTab] = useState('task')

  // 加载详情
  useEffect(() => {
    loadDetail()
  }, [writingId])

  const loadDetail = async () => {
    setLoading(true)
    try {
      const response = await getWritingDetail(writingId)
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
    setGenerating(true)
    try {
      await generateSample(writingId)
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
    try {
      await deleteSample(writingId, sampleId)
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

  const parseStructureLines = (value?: string): string[] => {
    if (!value) return []
    return value
      .split('\n')
      .map((item) => item.trim())
      .filter(Boolean)
  }

  // 渲染题目内容
  const renderTaskContent = () => {
    if (!detail) return null

    return (
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        <Card
          size="small"
          style={{
            background: 'linear-gradient(135deg, #f7fbff 0%, #eef7ff 100%)',
            border: '1px solid #d6eaff',
          }}
        >
          <Space direction="vertical" size={10} style={{ width: '100%' }}>
            <Space wrap size={[8, 8]}>
              <Tag color={getGroupColor(detail.group_category?.name)}>
                {detail.group_category?.name || '未识别'}
              </Tag>
              <Tag color="cyan">{detail.major_category?.name || '未分类'}</Tag>
              <Tag color="geekblue">{detail.category?.name || '未分类'}</Tag>
              <Tag color="purple">{detail.training_word_target || '150词左右'}</Tag>
            </Space>
            <div>
              <Text strong>分类路径</Text>
              <div style={{ marginTop: 4, color: '#4b5563' }}>
                {detail.group_category?.name || '未识别'} / {detail.major_category?.name || '未分类'} / {detail.category?.name || '未分类'}
              </div>
            </div>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                <Text strong>分类置信度</Text>
                <Text type="secondary">{Math.round((detail.category_confidence || 0) * 100)}%</Text>
              </div>
              <Progress percent={Math.round((detail.category_confidence || 0) * 100)} showInfo={false} strokeColor="#1677ff" />
            </div>
            {detail.category_reasoning && (
              <Alert
                type="info"
                showIcon
                message="分类说明"
                description={detail.category_reasoning}
              />
            )}
          </Space>
        </Card>

        {/* 基本信息 */}
        <Card size="small">
          <Descriptions column={2} bordered size="small">
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
        <Card size="small" title={<><FileTextOutlined /> 题目内容</>}>
          <Paragraph style={{ whiteSpace: 'pre-wrap', fontSize: 14, margin: 0 }}>
            {detail.task_content}
          </Paragraph>
          {detail.requirements && (
            <>
              <Divider style={{ margin: '12px 0' }} />
              <Title level={5} style={{ margin: '8px 0' }}>写作要求</Title>
              <Paragraph style={{ whiteSpace: 'pre-wrap', margin: 0 }}>
                {detail.requirements}
              </Paragraph>
            </>
          )}
        </Card>

        {/* 操作区 */}
        <Space wrap>
          <Button
            type="primary"
            size="small"
            icon={<FileTextOutlined />}
            loading={generating}
            onClick={handleGenerateSample}
          >
            生成范文
          </Button>
          <Button
            size="small"
            icon={<FilePdfOutlined />}
            onClick={handleExportPdf}
            disabled={!detail.templates?.length && !detail.samples?.length}
          >
            导出讲义
          </Button>
        </Space>
      </Space>
    )
  }

  // 渲染模板
  const renderTemplates = () => {
    if (!detail?.templates?.length) {
      return (
        <Empty
          description="暂无模板"
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        >
          <Button type="primary" size="small" onClick={handleGenerateSample}>
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
      <Space direction="vertical" size="small" style={{ width: '100%' }}>
        {detail.templates.map((template: WritingTemplate) => {
          const openingSentences = parseJsonField(template.opening_sentences)
          const closingSentences = parseJsonField(template.closing_sentences)
          const transitionWords = parseJsonField(template.transition_words)
          const advancedVocabulary = parseJsonField(template.advanced_vocabulary)
          const grammarPoints = parseJsonField(template.grammar_points)
          const structureLines = parseStructureLines(template.structure)

          return (
            <Space direction="vertical" size="small" style={{ width: '100%' }} key={template.id}>
              <Card
                size="small"
                style={{
                  background: 'linear-gradient(135deg, #fffaf2 0%, #fff7e8 100%)',
                  border: '1px solid #ffe0b2',
                }}
              >
                <Space direction="vertical" size={6}>
                  <Space wrap size={[8, 8]}>
                    <Tag color={getGroupColor(detail?.group_category?.name)}>{detail?.group_category?.name || '未识别'}</Tag>
                    <Tag color="cyan">{detail?.major_category?.name || '未分类'}</Tag>
                    <Tag color="orange">{detail?.category?.name || '未分类'}</Tag>
                  </Space>
                  <Text strong>{template.template_name}</Text>
                  <Text type="secondary">这个模板会在试卷导入后按子类生成，并供同类题复用。</Text>
                </Space>
              </Card>

              {/* 文章结构 */}
              {structureLines.length > 0 && (
                <Card size="small" title={<><BulbOutlined /> 文章结构</>}>
                  <List
                    size="small"
                    dataSource={structureLines}
                    renderItem={(item: string) => (
                      <List.Item style={{ padding: '6px 0' }}>
                        <Text style={{ fontSize: 13 }}>{item}</Text>
                      </List.Item>
                    )}
                  />
                </Card>
              )}

              {/* 模板内容 */}
              <Card size="small" title={<><FileTextOutlined /> 模板内容</>}>
                <Paragraph
                  style={{
                    whiteSpace: 'pre-wrap',
                    backgroundColor: '#f5f5f5',
                    padding: 12,
                    borderRadius: 6,
                    margin: 0,
                    fontSize: 13,
                  }}
                >
                  {template.template_content}
                </Paragraph>
              </Card>

              {/* 句型库 */}
              {(openingSentences.length > 0 || closingSentences.length > 0) && (
                <Row gutter={12}>
                  {openingSentences.length > 0 && (
                    <Col span={12}>
                      <Card
                        size="small"
                        title={<><ThunderboltOutlined /> 开头句型</>}
                        extra={<Tag color="blue" style={{ fontSize: 11 }}>{openingSentences.length}</Tag>}
                      >
                        <List
                          size="small"
                          dataSource={openingSentences}
                          renderItem={(item: string) => (
                            <List.Item
                              style={{ padding: '4px 0', fontSize: 12 }}
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
                              <Text style={{ fontSize: 12 }}>{item}</Text>
                            </List.Item>
                          )}
                        />
                      </Card>
                    </Col>
                  )}
                  {closingSentences.length > 0 && (
                    <Col span={12}>
                      <Card
                        size="small"
                        title={<><CheckCircleOutlined /> 结尾句型</>}
                        extra={<Tag color="green" style={{ fontSize: 11 }}>{closingSentences.length}</Tag>}
                      >
                        <List
                          size="small"
                          dataSource={closingSentences}
                          renderItem={(item: string) => (
                            <List.Item
                              style={{ padding: '4px 0' }}
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
                              <Text style={{ fontSize: 12 }}>{item}</Text>
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
                <Card size="small" title={<><RiseOutlined /> 过渡词汇</>}>
                  <Space wrap size={[4, 4]}>
                    {transitionWords.map((item: string, idx: number) => (
                      <Tag key={idx} color="purple" style={{ margin: 2, fontSize: 11 }}>
                        {item}
                      </Tag>
                    ))}
                  </Space>
                </Card>
              )}

              {/* 高级词汇替换 */}
              {advancedVocabulary.length > 0 && (
                <Card size="small" title={<><BookOutlined /> 高级词汇替换</>}>
                  <Space wrap size={[4, 4]}>
                    {advancedVocabulary.map((item: { word: string; basic: string }, idx: number) => (
                      <Tag key={idx} color="orange" style={{ margin: 2, fontSize: 11 }}>
                        {item.basic} → {item.word}
                      </Tag>
                    ))}
                  </Space>
                </Card>
              )}

              {/* 语法要点 */}
              {grammarPoints.length > 0 && (
                <Card size="small" title="语法要点">
                  <List
                    size="small"
                    dataSource={grammarPoints}
                    renderItem={(item: string) => (
                      <List.Item style={{ padding: '2px 0', fontSize: 12 }}>
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
                    <div style={{ whiteSpace: 'pre-wrap', fontSize: 12 }}>{template.tips}</div>
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
          <Button type="primary" size="small" onClick={handleGenerateSample}>
            生成范文
          </Button>
        </Empty>
      )
    }

    return (
      <Space direction="vertical" size="small" style={{ width: '100%' }}>
        {detail.samples.map((sample: WritingSample, index: number) => (
          <Card
            key={sample.id}
            size="small"
            title={
              <Space>
                <FileTextOutlined />
                范文 {index + 1}
                {sample.word_count && (
                  <Tag color="blue" style={{ fontSize: 11 }}>{sample.word_count} 词</Tag>
                )}
              </Space>
            }
            extra={
              <Space>
                {sample.score_level && (
                  <Tag color="gold" style={{ fontSize: 11 }}>{sample.score_level}</Tag>
                )}
                <Tag style={{ fontSize: 11 }}>{sample.sample_type}</Tag>
                <Popconfirm
                  title="确定删除这篇范文吗？"
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
                fontSize: 13,
                lineHeight: 1.7,
                margin: 0,
              }}
            >
              {sample.sample_content}
            </Paragraph>

            {/* 中文翻译 */}
            {sample.translation && (
              <Collapse
                style={{ marginTop: 12 }}
                size="small"
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
                          fontSize: 12,
                          lineHeight: 1.8,
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

            <Divider style={{ margin: '8px 0' }} />
            <Text type="secondary" style={{ fontSize: 11 }}>
              <ClockCircleOutlined /> {new Date(sample.created_at).toLocaleString()}
            </Text>
          </Card>
        ))}
      </Space>
    )
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 300 }}>
        <Spin size="large" tip="加载中..." />
      </div>
    )
  }

  if (!detail) {
    return (
      <div style={{ padding: 24, textAlign: 'center' }}>
        <Empty description="作文不存在" />
        <Button onClick={onClose}>关闭</Button>
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
        <Space size={4}>
          <BulbOutlined />
          模板
          {detail.templates?.length > 0 && (
            <Tag color="blue" style={{ fontSize: 10 }}>{detail.templates.length}</Tag>
          )}
        </Space>
      ),
      children: renderTemplates(),
    },
    {
      key: 'sample',
      label: (
        <Space size={4}>
          <FileTextOutlined />
          范文
          {detail.samples?.length > 0 && (
            <Tag color="green" style={{ fontSize: 10 }}>{detail.samples.length}</Tag>
          )}
        </Space>
      ),
      children: renderSamples(),
    },
  ]

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* 顶部标题栏 */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '12px 16px',
        borderBottom: '1px solid #f0f0f0',
        background: '#fafcff',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Button
            type="text"
            size="small"
            icon={<ArrowLeftOutlined />}
            onClick={onClose}
          >
            返回
          </Button>
          <Title level={5} style={{ margin: 0 }}>
            {detail.source?.grade || ''} {detail.source?.exam_type || ''} 作文
            {detail.category?.name && (
              <Text type="secondary" style={{ marginLeft: 8, fontSize: 12 }}>
                · {detail.category.name}
              </Text>
            )}
          </Title>
          {detail.group_category && (
            <Tag color={getGroupColor(detail.group_category.name)}>
              {detail.group_category.name}
            </Tag>
          )}
        </div>
        <Button
          type="text"
          size="small"
          icon={<CloseOutlined />}
          onClick={onClose}
        />
      </div>

      {/* 内容区 */}
      <div style={{ flex: 1, overflow: 'auto', padding: 16 }}>
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={tabItems}
          size="small"
        />
      </div>
    </div>
  )
}
