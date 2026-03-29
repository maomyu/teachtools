/**
 * 讲义转换页面
 *
 * [INPUT]: 依赖 antd 组件和 handoutService
 * [OUTPUT]: 对外提供 HandoutConverterPage 组件
 * [POS]: frontend/src/pages 的讲义转换页面
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */
import { useState, useCallback, useRef, type ChangeEvent } from 'react'
import {
  Card,
  Typography,
  Button,
  Progress,
  message,
  Space,
  Divider,
  Alert,
  Image,
  Result,
  Select,
  Row,
  Col,
} from 'antd'
import {
  UploadOutlined,
  PlayCircleOutlined,
  DownloadOutlined,
  ReloadOutlined,
  FileTextOutlined,
} from '@ant-design/icons'

import {
  uploadHandout,
  getProcessEventSourceUrl,
  getDownloadUrl,
  getWatermarkPreviewUrl,
} from '@/services/handoutService'

const { Title, Text, Paragraph } = Typography

interface ProcessState {
  status: 'idle' | 'uploaded' | 'processing' | 'completed' | 'error'
  taskId: string | null
  progress: number
  message: string
  answersRemoved: number
  error: string | null
}

export function HandoutConverterPage() {
  const [file, setFile] = useState<File | null>(null)
  const [watermarkDensity, setWatermarkDensity] = useState<'sparse' | 'medium' | 'dense'>('sparse')
  const [watermarkSize, setWatermarkSize] = useState<'small' | 'medium' | 'large'>('large')
  const watermarkPreviewUrl = getWatermarkPreviewUrl()
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const [processState, setProcessState] = useState<ProcessState>({
    status: 'idle',
    taskId: null,
    progress: 0,
    message: '',
    answersRemoved: 0,
    error: null,
  })

  const resetProcessState = () => {
    setProcessState({
      status: 'idle',
      taskId: null,
      progress: 0,
      message: '',
      answersRemoved: 0,
      error: null,
    })
  }

  const handleSelectFile = () => {
    if (processState.status === 'processing') return
    fileInputRef.current?.click()
  }

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const selectedFile = event.target.files?.[0] ?? null
    event.target.value = ''

    if (!selectedFile) {
      return
    }

    if (!selectedFile.name.toLowerCase().endsWith('.docx')) {
      message.error('只支持 .docx 文件')
      return
    }

    setFile(selectedFile)
    setWatermarkDensity('sparse')
    resetProcessState()
  }

  // 上传文件
  const handleUpload = async () => {
    if (!file) {
      message.warning('请先选择文件')
      return
    }

    try {
      setProcessState((prev) => ({ ...prev, status: 'processing', message: '正在上传...' }))

      const result = await uploadHandout(file)

      setProcessState({
        status: 'uploaded',
        taskId: result.task_id,
        progress: 10,
        message: '文件上传成功',
        answersRemoved: 0,
        error: null,
      })

      message.success(`文件上传成功: ${result.filename}`)
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail || '上传失败，请重试')
      setProcessState((prev) => ({
        ...prev,
        status: 'error',
        error: err.response?.data?.detail || '上传失败',
      }))
    }
  }

  // 开始处理
  const handleProcess = useCallback(() => {
    if (!processState.taskId) {
      message.warning('请先上传文件')
      return
    }

    setProcessState((prev) => ({ ...prev, status: 'processing', progress: 20, message: '开始处理...' }))

    const eventSource = new EventSource(
      getProcessEventSourceUrl(
        processState.taskId,
        watermarkDensity,
        watermarkSize
      )
    )

    eventSource.addEventListener('progress', (event) => {
      const data = JSON.parse(event.data)
      setProcessState((prev) => ({
        ...prev,
        progress: data.progress,
        message: data.message,
      }))
    })

    eventSource.addEventListener('completed', (event) => {
      const data = JSON.parse(event.data)
      setProcessState({
        status: 'completed',
        taskId: processState.taskId,
        progress: 100,
        message: '处理完成！',
        answersRemoved: data.answers_removed || 0,
        error: null,
      })
      eventSource.close()
      message.success('处理完成！')
    })

    eventSource.addEventListener('error', (event) => {
      if (event instanceof MessageEvent) {
        const data = JSON.parse(event.data)
        setProcessState((prev) => ({
          ...prev,
          status: 'error',
          error: data.error || '处理失败',
        }))
        message.error(data.error || '处理失败')
      }
      eventSource.close()
    })

    eventSource.onerror = () => {
      setProcessState((prev) => ({
        ...prev,
        status: 'error',
        error: '连接中断，请重试',
      }))
      eventSource.close()
      message.error('连接中断，请重试')
    }
  }, [processState.taskId, watermarkDensity, watermarkSize])

  // 下载 PDF
  const handleDownload = () => {
    if (!processState.taskId) return
    window.open(getDownloadUrl(processState.taskId), '_blank')
  }

  // 重置
  const handleReset = () => {
    setFile(null)
    setWatermarkDensity('sparse')
    setWatermarkSize('large')
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
    resetProcessState()
  }

  return (
    <div style={{ padding: 24, maxWidth: 800, margin: '0 auto' }}>
      <Card>
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          {/* 标题 */}
          <div>
            <Title level={3} style={{ marginBottom: 8 }}>
              <FileTextOutlined style={{ marginRight: 8 }} />
              教师版讲义转学生版
            </Title>
            <Text type="secondary">
              上传教师版 Word 讲义，系统将自动删除答案部分，并生成带图片水印的学生版 PDF
            </Text>
          </div>

          <Divider />

          {/* 文件上传区域 */}
          <div>
            <Text strong>1. 选择文件</Text>
            <div style={{ marginTop: 12 }}>
              <input
                ref={fileInputRef}
                type="file"
                accept=".docx,.DOCX,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                style={{ display: 'none' }}
                onChange={handleFileChange}
              />
              <Button icon={<UploadOutlined />} disabled={processState.status === 'processing'} onClick={handleSelectFile}>
                选择 Word 文件
              </Button>
              {file && (
                <Text type="secondary" style={{ marginLeft: 12 }}>
                  已选择: {file.name}
                </Text>
              )}
            </div>
          </div>

          {/* 水印设置 */}
          <div>
            <Text strong>2. 水印设置</Text>
            <div style={{ marginTop: 12 }}>
              <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                <Row gutter={16}>
                  <Col xs={24} md={12}>
                    <div>
                      <Text type="secondary" style={{ fontSize: 12 }}>固定图片水印</Text>
                      <div
                        style={{
                          marginTop: 8,
                          padding: 12,
                          border: '1px solid #f0f0f0',
                          borderRadius: 8,
                          background: '#fff',
                        }}
                      >
                        <Image
                          src={watermarkPreviewUrl}
                          alt="讲义图片水印预览"
                          preview={false}
                          style={{
                            width: '100%',
                            maxWidth: 320,
                            objectFit: 'contain',
                            display: 'block',
                          }}
                        />
                        <Text type="secondary" style={{ display: 'block', marginTop: 8, fontSize: 12 }}>
                          当前会自动使用这张图片做底层水印，不再叠加文字。
                        </Text>
                      </div>
                    </div>
                  </Col>
                  <Col xs={24} md={6}>
                    <div>
                      <Text type="secondary" style={{ fontSize: 12 }}>水印密度</Text>
                      <Select
                        value={watermarkDensity}
                        onChange={setWatermarkDensity}
                        style={{ width: '100%', marginTop: 4 }}
                        disabled={processState.status === 'processing'}
                        options={[
                          { label: '默认（单页1个）', value: 'sparse' },
                          { label: '适中', value: 'medium' },
                          { label: '密集', value: 'dense' },
                        ]}
                      />
                      <Text type="secondary" style={{ display: 'block', marginTop: 6, fontSize: 12 }}>
                        默认会在每页居中放置 1 个较大的完整水印，只有手动切换为“适中/密集”才会平铺。
                      </Text>
                    </div>
                  </Col>
                  <Col xs={24} md={6}>
                    <div>
                      <Text type="secondary" style={{ fontSize: 12 }}>水印大小</Text>
                      <Select
                        value={watermarkSize}
                        onChange={setWatermarkSize}
                        style={{ width: '100%', marginTop: 4 }}
                        disabled={processState.status === 'processing'}
                        options={[
                          { label: '小', value: 'small' },
                          { label: '中', value: 'medium' },
                          { label: '大', value: 'large' },
                        ]}
                      />
                    </div>
                  </Col>
                </Row>
              </Space>
            </div>
          </div>

          {/* 操作按钮 */}
          <div>
            <Text strong>3. 开始转换</Text>
            <div style={{ marginTop: 12 }}>
              <Space>
                <Button
                  type="primary"
                  onClick={handleUpload}
                  disabled={!file || processState.status === 'processing' || processState.status === 'uploaded'}
                  loading={processState.status === 'processing' && processState.progress < 30}
                >
                  <UploadOutlined />
                  上传文件
                </Button>

                <Button
                  type="primary"
                  onClick={handleProcess}
                  disabled={
                    !file ||
                    processState.status === 'idle' ||
                    processState.status === 'processing' ||
                    processState.status === 'completed'
                  }
                  loading={processState.status === 'processing'}
                >
                  <PlayCircleOutlined />
                  开始处理
                </Button>

                {(processState.status === 'completed' || processState.status === 'error') && (
                  <Button onClick={handleReset}>
                    <ReloadOutlined />
                    重新开始
                  </Button>
                )}
              </Space>
            </div>
          </div>

          {/* 进度显示 */}
          {(processState.status === 'processing' || processState.status === 'uploaded') && (
            <div>
              <Divider />
              <Progress
                percent={processState.progress}
                status={processState.status === 'processing' ? 'active' : 'success'}
              />
              <Text type="secondary">{processState.message}</Text>
            </div>
          )}

          {/* 错误提示 */}
          {processState.status === 'error' && (
            <Alert
              type="error"
              message="处理失败"
              description={processState.error}
              showIcon
            />
          )}

          {/* 完成状态 */}
          {processState.status === 'completed' && (
            <Result
              status="success"
              title="转换完成"
              subTitle={`已删除 ${processState.answersRemoved} 处答案内容`}
              extra={[
                <Button
                  type="primary"
                  key="download"
                  icon={<DownloadOutlined />}
                  onClick={handleDownload}
                  size="large"
                >
                  下载学生版 PDF
                </Button>,
              ]}
            />
          )}

          <Divider />

          {/* 使用说明 */}
          <Alert
            type="info"
            message="使用说明"
            description={
              <div>
                <Paragraph style={{ marginBottom: 8 }}>
                  1. 选择教师版 Word 讲义文件（.docx 格式）
                </Paragraph>
                <Paragraph style={{ marginBottom: 8 }}>
                  2. 点击"上传文件"将文件上传到服务器
                </Paragraph>
                <Paragraph style={{ marginBottom: 8 }}>
                  3. 点击"开始处理"，AI 将自动识别并删除答案内容
                </Paragraph>
                <Paragraph style={{ marginBottom: 8 }}>
                  4. 处理完成后点击"下载学生版 PDF"获取结果
                </Paragraph>
                <Paragraph type="warning" style={{ marginBottom: 0 }}>
                  注意：处理过程中请勿关闭页面，原文档中的图片将被保留
                </Paragraph>
              </div>
            }
          />
        </Space>
      </Card>
    </div>
  )
}
