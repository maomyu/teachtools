/**
 * [INPUT]: 依赖 @ant-design/icons 图标、antd 组件库、@/types 的 PipelineStep/StepUpdateEvent
 * [OUTPUT]: 对外提供 ImportPage 组件
 * [POS]: frontend/src/pages 的试卷导入页面，实现可扩展的步骤化进度监控
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */
import { useState, useCallback, useMemo } from 'react'
import {
  Card,
  Upload,
  Button,
  Table,
  message,
  Progress,
  Space,
  Typography,
  Tag,
  Alert,
  Statistic,
  Row,
  Col,
  Tooltip,
} from 'antd'
import {
  InboxOutlined,
  FileWordOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ExclamationCircleOutlined,
  ReloadOutlined,
  LoadingOutlined,
  MinusCircleOutlined,
} from '@ant-design/icons'
import type { UploadFile } from 'antd/es/upload/interface'
import type { ColumnsType } from 'antd/es/table'
import type {
  PipelineStep,
  StepUpdateEvent,
  StepStatus,
  ImportResult
} from '@/types'

const { Title, Text } = Typography
const { Dragger } = Upload

// ============================================================================
//  步骤状态图标与颜色映射
// ============================================================================

const statusConfig: Record<StepStatus, { icon: React.ReactNode; color: string }> = {
  pending: { icon: <MinusCircleOutlined />, color: '#d9d9d9' },
  running: { icon: <LoadingOutlined spin />, color: '#1890ff' },
  completed: { icon: <CheckCircleOutlined />, color: '#52c41a' },
  failed: { icon: <CloseCircleOutlined />, color: '#ff4d4f' },
  skipped: { icon: <ExclamationCircleOutlined />, color: '#faad14' },
}


// ============================================================================
//  子组件：单个步骤渲染
// ============================================================================

interface StepItemProps {
  step: PipelineStep
  isCurrent: boolean
}

function StepItem({ step, isCurrent }: StepItemProps) {
  const config = statusConfig[step.status]

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        padding: '8px 12px',
        marginBottom: 4,
        borderRadius: 6,
        backgroundColor: isCurrent ? '#f0f5ff' : 'transparent',
        border: isCurrent ? '1px solid #adc6ff' : '1px solid transparent',
        transition: 'all 0.3s ease',
      }}
    >
      {/* 图标 + 名称 */}
      <div style={{ display: 'flex', alignItems: 'center', width: 160, flexShrink: 0 }}>
        <span style={{ fontSize: 16, marginRight: 8, color: config.color }}>
          {config.icon}
        </span>
        <Tooltip title={step.description}>
          <Text
            strong={isCurrent}
            style={{ color: step.status === 'failed' ? '#ff4d4f' : undefined }}
          >
            {step.icon} {step.name}
          </Text>
        </Tooltip>
      </div>

      {/* 进度条 */}
      <div style={{ flex: 1, margin: '0 12px' }}>
        {step.status === 'running' && (
          <Progress
            percent={step.progress}
            size="small"
            showInfo={false}
            strokeColor="#1890ff"
            trailColor="#f0f0f0"
          />
        )}
      </div>

      {/* 消息/状态 */}
      <div style={{ width: 200, textAlign: 'right', flexShrink: 0 }}>
        {step.status === 'running' && step.message && (
          <Text type="secondary" style={{ fontSize: 12 }}>
            {step.message}
          </Text>
        )}
        {step.status === 'completed' && step.message && (
          <Text style={{ color: '#52c41a', fontSize: 12 }}>
            ✓ {step.message}
          </Text>
        )}
        {step.status === 'failed' && step.error && (
          <Text type="danger" style={{ fontSize: 12 }}>
            {step.error}
          </Text>
        )}
        {step.status === 'skipped' && step.message && (
          <Text type="warning" style={{ fontSize: 12 }}>
            跳过: {step.message}
          </Text>
        )}
        {step.status === 'pending' && (
          <Text type="secondary" style={{ fontSize: 12 }}>
            等待中
          </Text>
        )}
      </div>
    </div>
  )
}

// ============================================================================
//  主组件
// ============================================================================

export function ImportPage() {
  const [fileList, setFileList] = useState<UploadFile[]>([])
  const [uploading, setUploading] = useState(false)
  const [results, setResults] = useState<ImportResult[]>([])

  // 步骤化进度状态
  const [steps, setSteps] = useState<PipelineStep[]>([])
  const [currentStep, setCurrentStep] = useState<string | null>(null)
  const [overallProgress, setOverallProgress] = useState(0)
  const [currentFileIndex, setCurrentFileIndex] = useState(0)


  // 解析SSE事件
  const parseSSEEvent = useCallback((line: string): StepUpdateEvent | null => {
    if (!line.startsWith('data: ')) return null
    try {
      return JSON.parse(line.slice(6)) as StepUpdateEvent
    } catch {
      return null
    }
  }, [])

  // 使用SSE上传单个文件
  const uploadWithProgress = useCallback(async (file: UploadFile): Promise<ImportResult> => {
    return new Promise((resolve, reject) => {
      const formData = new FormData()
      // 获取原始文件对象
      const rawFile = file.originFileObj || file
      formData.append('file', rawFile as any)

      const params = new URLSearchParams()
      params.append('force', 'true')  // 总是强制导入

      fetch(`/api/papers/upload-with-progress?${params.toString()}`, {
        method: 'POST',
        body: formData,
      })
        .then(async (response) => {
          const reader = response.body?.getReader()
          if (!reader) {
            reject(new Error('无法读取响应流'))
            return
          }

          const decoder = new TextDecoder()
          let lastResult: ImportResult | null = null

          while (true) {
            const { done, value } = await reader.read()
            if (done) break

            const text = decoder.decode(value)
            const lines = text.split('\n')

            for (const line of lines) {
              const event = parseSSEEvent(line)
              if (!event) continue

              // 更新步骤状态
              setSteps(event.steps)
              setCurrentStep(event.current_step)
              setOverallProgress(event.overall_progress)

              // 记录最终结果
              if (event.type === 'completed' && event.result) {
                lastResult = event.result
              }
            }
          }

          if (lastResult) {
            resolve(lastResult)
          } else {
            resolve({
              status: 'error',
              filename: file.name,
              error: '未收到完成信号',
            })
          }
        })
        .catch((error) => {
          reject(error)
        })
    })
  }, [parseSSEEvent])

  // 处理文件上传
  const handleUpload = async () => {
    if (fileList.length === 0) {
      message.warning('请先选择要上传的文件')
      return
    }

    setUploading(true)
    setOverallProgress(0)
    setResults([])
    setSteps([])
    setCurrentStep(null)

    const uploadResults: ImportResult[] = []

    for (let i = 0; i < fileList.length; i++) {
      const file = fileList[i]
      setCurrentFileIndex(i + 1)

      try {
        const result = await uploadWithProgress(file)  // 强制导入
        uploadResults.push(result)
        setResults([...uploadResults])
      } catch (error: any) {
        uploadResults.push({
          status: 'error',
          filename: file.name,
          error: error.message || '上传失败',
        })
        setResults([...uploadResults])
      }
    }

    setUploading(false)
    setCurrentStep(null)

    // 统计结果
    const successCount = uploadResults.filter(r => r.status === 'success').length
    const failedCount = uploadResults.filter(r => r.status === 'failed' || r.status === 'error').length
    const existsCount = uploadResults.filter(r => r.status === 'exists').length

    if (successCount > 0) {
      message.success(`成功导入 ${successCount} 份试卷`)
    }
    if (failedCount > 0) {
      message.error(`${failedCount} 份试卷导入失败`)
    }
    if (existsCount > 0) {
      message.warning(`${existsCount} 份试卷已存在`)
    }
  }

  // 清空结果
  const handleClear = () => {
    setFileList([])
    setResults([])
    setOverallProgress(0)
    setSteps([])
    setCurrentStep(null)
  }

  // 结果表格列定义
  const columns: ColumnsType<ImportResult> = [
    {
      title: '文件名',
      dataIndex: 'filename',
      key: 'filename',
      width: 250,
      render: (text: string) => (
        <Space>
          <FileWordOutlined />
          <Text ellipsis style={{ maxWidth: 200 }}>{text}</Text>
        </Space>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => {
        const config: Record<string, { color: string; icon: React.ReactNode; text: string }> = {
          success: { color: 'success', icon: <CheckCircleOutlined />, text: '成功' },
          failed: { color: 'error', icon: <CloseCircleOutlined />, text: '失败' },
          error: { color: 'error', icon: <CloseCircleOutlined />, text: '错误' },
          exists: { color: 'warning', icon: <ExclamationCircleOutlined />, text: '已存在' },
        }
        const { color, icon, text } = config[status] || config.error
        return (
          <Tag color={color} icon={icon}>
            {text}
          </Tag>
        )
      },
    },
    {
      title: '出处信息',
      key: 'metadata',
      width: 200,
      render: (_, record) => {
        if (!record.metadata) return '-'
        const { year, region, grade, exam_type } = record.metadata
        return (
          <span>
            {year} {region} {grade} {exam_type}
          </span>
        )
      },
    },
    {
      title: '文章/题目数',
      key: 'counts',
      width: 100,
      render: (_, record) => {
        if (record.passages_created === undefined) return '-'
        return `${record.passages_created}篇 / ${record.questions_created || 0}题`
      },
    },
    {
      title: '解析策略',
      dataIndex: 'parse_strategy',
      key: 'parse_strategy',
      width: 100,
      render: (strategy: string) => {
        if (!strategy) return '-'
        const strategyMap: Record<string, { text: string; color: string }> = {
          rule: { text: '规则解析', color: 'blue' },
          llm: { text: 'AI解析', color: 'purple' },
          manual: { text: '人工标注', color: 'orange' },
        }
        const config = strategyMap[strategy] || { text: strategy, color: 'default' }
        return <Tag color={config.color}>{config.text}</Tag>
      },
    },
    {
      title: '错误信息',
      dataIndex: 'error',
      key: 'error',
      ellipsis: true,
      render: (error: string) => error || '-',
    },
  ]

  // 统计信息
  const successCount = results.filter(r => r.status === 'success').length
  const failedCount = results.filter(r => r.status === 'failed' || r.status === 'error').length
  const totalPassages = results.reduce((sum, r) => sum + (r.passages_created || 0), 0)
  const totalQuestions = results.reduce((sum, r) => sum + (r.questions_created || 0), 0)

  // 当前步骤名称
  const currentStepName = useMemo(() => {
    const step = steps.find(s => s.id === currentStep)
    return step?.name || ''
  }, [steps, currentStep])

  return (
    <div>
      <Title level={3}>试卷导入</Title>

      {/* 上传区域 */}
      <Card style={{ marginBottom: 16 }}>
        <Dragger
          multiple
          accept=".docx"
          fileList={fileList}
          beforeUpload={(file, _fileList) => {
            // 批量添加文件
            if (!file.name.endsWith('.docx')) {
              message.error(`${file.name} 不是 .docx 格式`)
              return false
            }
            return false  // 阻止自动上传
          }}
          onChange={(info) => {
            // 只保留 .docx 文件
            const docxFiles = info.fileList.filter(
              f => f.name.endsWith('.docx') || (f as any).originFileObj?.name?.endsWith('.docx')
            )
            setFileList(docxFiles)
          }}
          onRemove={(file) => {
            const index = fileList.indexOf(file)
            const newFileList = fileList.slice()
            newFileList.splice(index, 1)
            setFileList(newFileList)
          }}
        >
          <p className="ant-upload-drag-icon">
            <InboxOutlined />
          </p>
          <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
          <p className="ant-upload-hint">
            支持批量上传 .docx 格式的试卷文件（可一次选择多个文件）
          </p>
        </Dragger>

        {/* 选择文件夹按钮 */}
        <div style={{ marginTop: 12, textAlign: 'center' }}>
          <input
            type="file"
            // @ts-ignore - webkitdirectory 是非标准属性
            webkitdirectory="true"
            directory=""
            multiple
            style={{ display: 'none' }}
            id="folder-input"
            onChange={(e) => {
              const files = e.target.files
              if (files) {
                const docxFiles = Array.from(files).filter(f => f.name.endsWith('.docx'))
                if (docxFiles.length === 0) {
                  message.warning('所选文件夹中没有 .docx 文件')
                  return
                }
                const newFiles = docxFiles.map(f => ({
                  uid: `${Date.now()}-${f.name}`,
                  name: f.name,
                  status: 'done' as const,
                  originFileObj: f,
                })) as UploadFile[]
                setFileList(prev => [...prev, ...newFiles])
                message.success(`已添加 ${docxFiles.length} 个 .docx 文件`)
              }
              // 重置 input 以便再次选择同一文件夹
              e.target.value = ''
            }}
          />
          <Button
            onClick={() => document.getElementById('folder-input')?.click()}
            icon={<InboxOutlined />}
            style={{ marginRight: 8 }}
          >
            选择文件夹
          </Button>
          <Text type="secondary">
            点击可选择整个文件夹（自动筛选 .docx 文件）
          </Text>
        </div>

        <div style={{ marginTop: 16, textAlign: 'center' }}>
          <Space direction="vertical" size="middle">
            <Space>
              <Button
                type="primary"
                onClick={handleUpload}
                loading={uploading}
                disabled={fileList.length === 0}
                icon={<FileWordOutlined />}
              >
                开始导入 ({fileList.length} 个文件)
              </Button>
              <Button onClick={handleClear} icon={<ReloadOutlined />}>
                清空
              </Button>
            </Space>
          </Space>
        </div>

        {/* 步骤化进度展示 */}
        {uploading && steps.length > 0 && (
          <Card
            style={{ marginTop: 16 }}
            size="small"
            title={
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span>
                  正在处理: 第 {currentFileIndex} / {fileList.length} 个文件
                </span>
                <Tag color="blue">{fileList[currentFileIndex - 1]?.name}</Tag>
              </div>
            }
          >
            {/* 总体进度 */}
            <div style={{ marginBottom: 16 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                <Text strong>总体进度</Text>
                <Text type="secondary">{currentStepName}</Text>
              </div>
              <Progress
                percent={overallProgress}
                status={overallProgress === 100 ? 'success' : 'active'}
                strokeColor={{
                  '0%': '#108ee9',
                  '100%': '#87d068',
                }}
              />
            </div>

            {/* 步骤列表 */}
            <div style={{ border: '1px solid #f0f0f0', borderRadius: 8, padding: 8 }}>
              {steps.map((step) => (
                <StepItem
                  key={step.id}
                  step={step}
                  isCurrent={step.id === currentStep}
                />
              ))}
            </div>
          </Card>
        )}
      </Card>

      {/* 统计信息 */}
      {results.length > 0 && (
        <Card style={{ marginBottom: 16 }}>
          <Row gutter={16}>
            <Col span={4}>
              <Statistic
                title="总文件数"
                value={results.length}
                prefix={<FileWordOutlined />}
              />
            </Col>
            <Col span={4}>
              <Statistic
                title="成功导入"
                value={successCount}
                valueStyle={{ color: '#3f8600' }}
                prefix={<CheckCircleOutlined />}
              />
            </Col>
            <Col span={4}>
              <Statistic
                title="导入失败"
                value={failedCount}
                valueStyle={{ color: '#cf1322' }}
                prefix={<CloseCircleOutlined />}
              />
            </Col>
            <Col span={4}>
              <Statistic
                title="提取文章"
                value={totalPassages}
                valueStyle={{ color: '#1890ff' }}
                suffix="篇"
              />
            </Col>
            <Col span={4}>
              <Statistic
                title="提取题目"
                value={totalQuestions}
                valueStyle={{ color: '#722ed1' }}
                suffix="题"
              />
            </Col>
            <Col span={4}>
              <Statistic
                title="已存在"
                value={results.filter(r => r.status === 'exists').length}
                valueStyle={{ color: '#faad14' }}
                prefix={<ExclamationCircleOutlined />}
              />
            </Col>
          </Row>
        </Card>
      )}

      {/* 导入结果 */}
      {results.length > 0 && (
        <Card title="导入结果">
          <Table
            columns={columns}
            dataSource={results}
            rowKey={(record) => record.filename}
            pagination={false}
            size="small"
          />
        </Card>
      )}

      {/* 使用说明 */}
      <Card title="使用说明" style={{ marginTop: 16 }}>
        <Alert
          message="支持的文件命名格式"
          description={
            <div>
              <p>推荐格式：年份 + 北京 + 区县 + 年级 + 学期 + 考试类型 + 英语 + 版本.docx</p>
              <p>示例：2023北京海淀初三（上）期末英语（教师版）.docx</p>
              <p>系统会自动解析文件名提取：年份、区县、年级、学期、考试类型等信息</p>
              <p style={{ marginTop: 8, color: '#722ed1' }}>
                <strong>AI解析流程：</strong>
                上传文件 → 解析文件名 → 上传AI服务 → AI提取C/D篇阅读和题目 → 保存数据 → AI话题分类 → 词汇提取
              </p>
            </div>
          }
          type="info"
          showIcon
        />
      </Card>
    </div>
  )
}
