/**
 * 试卷导入页面
 */
import { useState } from 'react'
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
} from 'antd'
import {
  InboxOutlined,
  FileWordOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ExclamationCircleOutlined,
  ReloadOutlined,
} from '@ant-design/icons'
import type { UploadFile } from 'antd/es/upload/interface'
import type { ColumnsType } from 'antd/es/table'

import api from '@/services/api'

const { Title, Text } = Typography
const { Dragger } = Upload

interface ImportResult {
  status: 'success' | 'failed' | 'error' | 'exists'
  filename: string
  paper_id?: number
  passages_created?: number
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

export function ImportPage() {
  const [fileList, setFileList] = useState<UploadFile[]>([])
  const [uploading, setUploading] = useState(false)
  const [results, setResults] = useState<ImportResult[]>([])
  const [progress, setProgress] = useState(0)
  const [forceReimport, setForceReimport] = useState(false)
  const [useLLM, setUseLLM] = useState(true)  // 默认使用LLM解析

  // 处理文件上传
  const handleUpload = async () => {
    if (fileList.length === 0) {
      message.warning('请先选择要上传的文件')
      return
    }

    setUploading(true)
    setProgress(0)
    setResults([])

    const uploadResults: ImportResult[] = []
    const totalFiles = fileList.length

    for (let i = 0; i < fileList.length; i++) {
      const file = fileList[i]
      setProgress(Math.round(((i + 1) / totalFiles) * 100))

      const formData = new FormData()
      formData.append('file', file as any)

      try {
        const params = new URLSearchParams()
        if (forceReimport) params.append('force', 'true')
        if (useLLM) params.append('use_llm', 'true')

        const response = await api.post<ImportResult>(
          `/papers/upload?${params.toString()}`,
          formData,
          {
            headers: {
              'Content-Type': 'multipart/form-data',
            },
          }
        )
        uploadResults.push(response.data)
      } catch (error: any) {
        uploadResults.push({
          status: 'error',
          filename: file.name,
          error: error.response?.data?.detail || '上传失败',
        })
      }

      setResults([...uploadResults])
    }

    setUploading(false)

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
      title: '文章数',
      dataIndex: 'passages_created',
      key: 'passages_created',
      width: 80,
      render: (count: number) => count || '-',
    },
    {
      title: '解析策略',
      dataIndex: 'parse_strategy',
      key: 'parse_strategy',
      width: 100,
      render: (strategy: string) => {
        if (!strategy) return '-'
        const strategyMap: Record<string, string> = {
          rule: '规则解析',
          llm: 'LLM辅助',
          manual: '人工标注',
        }
        return strategyMap[strategy] || strategy
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

        {uploading && (
          <div style={{ marginTop: 16 }}>
            <Progress percent={progress} status="active" />
          </div>
        )}
      </Card>

      {/* 统计信息 */}
      {results.length > 0 && (
        <Card style={{ marginBottom: 16 }}>
          <Row gutter={16}>
            <Col span={6}>
              <Statistic
                title="总文件数"
                value={results.length}
                prefix={<FileWordOutlined />}
              />
            </Col>
            <Col span={6}>
              <Statistic
                title="成功导入"
                value={successCount}
                valueStyle={{ color: '#3f8600' }}
                prefix={<CheckCircleOutlined />}
              />
            </Col>
            <Col span={6}>
              <Statistic
                title="导入失败"
                value={failedCount}
                valueStyle={{ color: '#cf1322' }}
                prefix={<CloseCircleOutlined />}
              />
            </Col>
            <Col span={6}>
              <Statistic
                title="提取文章数"
                value={totalPassages}
                valueStyle={{ color: '#1890ff' }}
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
