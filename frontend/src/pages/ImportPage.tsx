/**
 * 试卷导入页面 - 支持SSE实时进度展示
 */
import { useState, useCallback } from 'react'
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
  Checkbox,
  Steps,
  Spin,
} from 'antd'
import {
  InboxOutlined,
  FileWordOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ExclamationCircleOutlined,
  ReloadOutlined,
  CloudUploadOutlined,
  RobotOutlined,
  DatabaseOutlined,
  LoadingOutlined,
} from '@ant-design/icons'
import type { UploadFile } from 'antd/es/upload/interface'
import type { ColumnsType } from 'antd/es/table'

const { Title, Text } = Typography
const { Dragger } = Upload

// ============================================================================
//  类型定义
// ============================================================================

/** 处理阶段 */
type ProcessStage =
  | 'idle'
  | 'uploading'
  | 'uploaded'
  | 'parsing_filename'
  | 'parsed_filename'
  | 'uploading_to_ai'
  | 'uploaded_to_ai'
  | 'ai_parsing'
  | 'ai_parsed'
  | 'saving'
  | 'completed'
  | 'error'

/** SSE进度事件 */
interface ProgressEvent {
  stage: ProcessStage
  message: string
  progress: number
  metadata?: {
    year?: number
    region?: string
    grade?: string
    exam_type?: string
  }
  result?: ImportResult
}

/** 导入结果 */
interface ImportResult {
  status: 'success' | 'failed' | 'error' | 'exists'
  filename: string
  paper_id?: number
  passages_created?: number
  questions_created?: number
  error?: string
  message?: string
  metadata?: {
    year?: number
    region?: string
    grade?: string
    exam_type?: string
  }
  parse_strategy?: string
  confidence?: number
}

// ============================================================================
//  阶段配置
// ============================================================================

const stageConfig: Record<ProcessStage, { icon: React.ReactNode; color: string; stepIndex: number }> = {
  idle: { icon: <ExclamationCircleOutlined />, color: '#999', stepIndex: -1 },
  uploading: { icon: <LoadingOutlined spin />, color: '#1890ff', stepIndex: 0 },
  uploaded: { icon: <CheckCircleOutlined />, color: '#52c41a', stepIndex: 0 },
  parsing_filename: { icon: <LoadingOutlined spin />, color: '#1890ff', stepIndex: 1 },
  parsed_filename: { icon: <CheckCircleOutlined />, color: '#52c41a', stepIndex: 1 },
  uploading_to_ai: { icon: <CloudUploadOutlined />, color: '#1890ff', stepIndex: 2 },
  uploaded_to_ai: { icon: <CheckCircleOutlined />, color: '#52c41a', stepIndex: 2 },
  ai_parsing: { icon: <RobotOutlined />, color: '#722ed1', stepIndex: 3 },
  ai_parsed: { icon: <CheckCircleOutlined />, color: '#52c41a', stepIndex: 3 },
  saving: { icon: <DatabaseOutlined />, color: '#1890ff', stepIndex: 4 },
  completed: { icon: <CheckCircleOutlined />, color: '#52c41a', stepIndex: 5 },
  error: { icon: <CloseCircleOutlined />, color: '#ff4d4f', stepIndex: -1 },
}

const stageText: Record<ProcessStage, string> = {
  idle: '等待上传',
  uploading: '上传文件中...',
  uploaded: '文件上传完成',
  parsing_filename: '解析文件名...',
  parsed_filename: '文件名解析完成',
  uploading_to_ai: '上传到AI服务...',
  uploaded_to_ai: 'AI服务已就绪',
  ai_parsing: '🤖 AI正在解析文档...',
  ai_parsed: 'AI解析完成',
  saving: '保存数据中...',
  completed: '✅ 导入完成',
  error: '❌ 发生错误',
}

// ============================================================================
//  组件
// ============================================================================

export function ImportPage() {
  const [fileList, setFileList] = useState<UploadFile[]>([])
  const [uploading, setUploading] = useState(false)
  const [results, setResults] = useState<ImportResult[]>([])

  // SSE进度状态
  const [currentStage, setCurrentStage] = useState<ProcessStage>('idle')
  const [progressMessage, setProgressMessage] = useState('')
  const [progress, setProgress] = useState(0)
  const [currentFileIndex, setCurrentFileIndex] = useState(0)

  const [forceReimport, setForceReimport] = useState(false)
  const [useLLM, setUseLLM] = useState(true)

  // 使用SSE上传单个文件
  const uploadWithProgress = useCallback(async (file: UploadFile): Promise<ImportResult> => {
    return new Promise((resolve, reject) => {
      const formData = new FormData()
      formData.append('file', file as any)

      const params = new URLSearchParams()
      if (forceReimport) params.append('force', 'true')
      if (useLLM) params.append('use_llm', 'true')

      // 使用fetch读取SSE流
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
              if (line.startsWith('data: ')) {
                try {
                  const event: ProgressEvent = JSON.parse(line.slice(6))
                  setCurrentStage(event.stage)
                  setProgressMessage(event.message)
                  setProgress(event.progress)

                  if (event.stage === 'completed' && event.result) {
                    lastResult = event.result
                  }
                  if (event.stage === 'error') {
                    lastResult = {
                      status: 'error',
                      filename: file.name,
                      error: event.message,
                    }
                  }
                } catch {
                  // 忽略解析错误
                }
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
  }, [forceReimport, useLLM])

  // 处理文件上传
  const handleUpload = async () => {
    if (fileList.length === 0) {
      message.warning('请先选择要上传的文件')
      return
    }

    setUploading(true)
    setProgress(0)
    setResults([])
    setCurrentStage('idle')
    setProgressMessage('')

    const uploadResults: ImportResult[] = []

    for (let i = 0; i < fileList.length; i++) {
      const file = fileList[i]
      setCurrentFileIndex(i + 1)

      try {
        const result = await uploadWithProgress(file)
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
    setCurrentStage('idle')

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
    setProgress(0)
    setCurrentStage('idle')
    setProgressMessage('')
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

  // 获取当前步骤索引
  const getCurrentStep = () => {
    if (currentStage === 'idle' || currentStage === 'error') return -1
    return stageConfig[currentStage]?.stepIndex ?? -1
  }

  return (
    <div>
      <Title level={3}>试卷导入</Title>

      {/* 上传区域 */}
      <Card style={{ marginBottom: 16 }}>
        <Dragger
          multiple
          accept=".docx"
          fileList={fileList}
          beforeUpload={(file) => {
            if (!file.name.endsWith('.docx')) {
              message.error('只支持 .docx 格式的文件')
              return false
            }
            setFileList([...fileList, file as unknown as UploadFile])
            return false
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
            支持批量上传 .docx 格式的试卷文件
          </p>
        </Dragger>

        <div style={{ marginTop: 16, textAlign: 'center' }}>
          <Space direction="vertical" size="middle">
            <Space>
              <Checkbox
                checked={useLLM}
                onChange={(e) => setUseLLM(e.target.checked)}
              >
                使用AI解析（更准确）
              </Checkbox>
              <Checkbox
                checked={forceReimport}
                onChange={(e) => setForceReimport(e.target.checked)}
              >
                强制重新导入
              </Checkbox>
            </Space>
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

        {/* SSE进度展示 */}
        {uploading && (
          <Card style={{ marginTop: 16 }} size="small">
            <Space direction="vertical" style={{ width: '100%' }} size="middle">
              {/* 当前文件信息 */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Text strong>
                  正在处理: 第 {currentFileIndex} / {fileList.length} 个文件
                </Text>
                <Tag color="blue">{fileList[currentFileIndex - 1]?.name}</Tag>
              </div>

              {/* 进度条 */}
              <Progress
                percent={progress}
                status={currentStage === 'error' ? 'exception' : 'active'}
                strokeColor={stageConfig[currentStage]?.color}
              />

              {/* 当前步骤 */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Spin spinning={currentStage !== 'completed' && currentStage !== 'error'} />
                <Text
                  strong
                  style={{ color: stageConfig[currentStage]?.color }}
                >
                  {progressMessage || stageText[currentStage]}
                </Text>
              </div>

              {/* 步骤指示器 */}
              {useLLM && (
                <Steps
                  current={getCurrentStep()}
                  size="small"
                  items={[
                    { title: '上传', icon: <CloudUploadOutlined /> },
                    { title: '解析文件名', icon: <FileWordOutlined /> },
                    { title: 'AI准备', icon: <CloudUploadOutlined /> },
                    { title: 'AI解析', icon: <RobotOutlined /> },
                    { title: '保存', icon: <DatabaseOutlined /> },
                  ]}
                />
              )}
            </Space>
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
            </div>
          }
          type="info"
          showIcon
        />
      </Card>
    </div>
  )
}
