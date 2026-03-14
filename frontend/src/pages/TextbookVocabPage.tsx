/**
 * 课本单词表页面
 *
 * 提供课本单词的浏览、搜索、增删改查功能
 * 用于熟词僻义判断的参照基准
 */
import { useState, useEffect, useCallback } from 'react'
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
  Row,
  Col,
  Modal,
  Form,
  Popconfirm,
  Statistic,
  Divider,
} from 'antd'
import {
  SearchOutlined,
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  ReloadOutlined,
  BookOutlined,
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'

import {
  getTextbookVocabList,
  getTextbookVocabStats,
  createTextbookVocab,
  updateTextbookVocab,
  deleteTextbookVocab,
  batchDeleteTextbookVocab,
} from '@/services/textbookService'
import type { TextbookVocab, TextbookVocabStats, TextbookVocabCreate } from '@/services/textbookService'

const { Text, Title } = Typography
const { Search } = Input

// 出版社选项
const PUBLISHER_OPTIONS = [
  { value: '人教版', label: '人教版' },
  { value: '外研版', label: '外研版' },
]

// 年级选项
const GRADE_OPTIONS = [
  { value: '七年级', label: '七年级' },
  { value: '八年级', label: '八年级' },
  { value: '九年级', label: '九年级' },
]

// 学期选项
const SEMESTER_OPTIONS = [
  { value: '上', label: '上学期' },
  { value: '下', label: '下学期' },
]

export function TextbookVocabPage() {
  // 状态管理
  const [loading, setLoading] = useState(false)
  const [vocabList, setVocabList] = useState<TextbookVocab[]>([])
  const [total, setTotal] = useState(0)
  const [stats, setStats] = useState<TextbookVocabStats | null>(null)

  // 筛选条件
  const [publisher, setPublisher] = useState<string | undefined>()
  const [grade, setGrade] = useState<string | undefined>()
  const [semester, setSemester] = useState<string | undefined>()
  const [keyword, setKeyword] = useState<string | undefined>()

  // 分页
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)

  // 选中行
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])

  // 弹窗
  const [modalOpen, setModalOpen] = useState(false)
  const [editingVocab, setEditingVocab] = useState<TextbookVocab | null>(null)
  const [form] = Form.useForm()

  // 加载数据
  useEffect(() => {
    loadVocabList()
    loadStats()
  }, [publisher, grade, semester, keyword, page, pageSize])

  const loadVocabList = async () => {
    setLoading(true)
    try {
      const response = await getTextbookVocabList({
        page,
        page_size: pageSize,
        publisher,
        grade,
        semester,
        keyword,
      })
      setVocabList(response.items)
      setTotal(response.total)
    } catch (error) {
      message.error('加载单词列表失败')
      console.error(error)
    } finally {
      setLoading(false)
    }
  }

  const loadStats = async () => {
    try {
      const data = await getTextbookVocabStats()
      setStats(data)
    } catch (error) {
      console.error('加载统计信息失败:', error)
    }
  }

  // 搜索
  const handleSearch = (value: string) => {
    setKeyword(value.trim() || undefined)
    setPage(1)
  }

  // 重置筛选
  const handleReset = () => {
    setPublisher(undefined)
    setGrade(undefined)
    setSemester(undefined)
    setKeyword(undefined)
    setPage(1)
  }

  // 打开新增弹窗
  const handleAdd = () => {
    setEditingVocab(null)
    form.resetFields()
    setModalOpen(true)
  }

  // 打开编辑弹窗
  const handleEdit = (record: TextbookVocab) => {
    setEditingVocab(record)
    form.setFieldsValue(record)
    setModalOpen(true)
  }

  // 保存单词
  const handleSave = async () => {
    try {
      const values = await form.validateFields()
      if (editingVocab) {
        await updateTextbookVocab(editingVocab.id, values)
        message.success('更新成功')
      } else {
        await createTextbookVocab(values as TextbookVocabCreate)
        message.success('添加成功')
      }
      setModalOpen(false)
      loadVocabList()
      loadStats()
    } catch (error) {
      message.error('保存失败')
      console.error(error)
    }
  }

  // 删除单词
  const handleDelete = async (id: number) => {
    try {
      await deleteTextbookVocab(id)
      message.success('删除成功')
      loadVocabList()
      loadStats()
    } catch (error) {
      message.error('删除失败')
      console.error(error)
    }
  }

  // 批量删除
  const handleBatchDelete = async () => {
    if (selectedRowKeys.length === 0) {
      message.warning('请先选择要删除的单词')
      return
    }
    try {
      await batchDeleteTextbookVocab(selectedRowKeys as number[])
      message.success(`成功删除 ${selectedRowKeys.length} 个单词`)
      setSelectedRowKeys([])
      loadVocabList()
      loadStats()
    } catch (error) {
      message.error('批量删除失败')
      console.error(error)
    }
  }

  // 表格列配置
  const columns: ColumnsType<TextbookVocab> = [
    {
      title: '单词',
      dataIndex: 'word',
      key: 'word',
      width: 150,
      render: (word: string) => <Text strong>{word}</Text>,
    },
    {
      title: '词性',
      dataIndex: 'pos',
      key: 'pos',
      width: 100,
      render: (pos: string | null) => pos ? <Tag color="blue">{pos}</Tag> : <Text type="secondary">-</Text>,
    },
    {
      title: '释义',
      dataIndex: 'definition',
      key: 'definition',
      ellipsis: true,
    },
    {
      title: '出版社',
      dataIndex: 'publisher',
      key: 'publisher',
      width: 80,
      render: (pub: string) => (
        <Tag color={pub === '人教版' ? 'green' : 'orange'}>{pub}</Tag>
      ),
    },
    {
      title: '年级',
      dataIndex: 'grade',
      key: 'grade',
      width: 80,
    },
    {
      title: '学期',
      dataIndex: 'semester',
      key: 'semester',
      width: 80,
      render: (sem: string) => sem === '上' ? '上学期' : '下学期',
    },
    {
      title: '单元',
      dataIndex: 'unit',
      key: 'unit',
      width: 120,
      ellipsis: true,
      render: (unit: string | null) => unit || <Text type="secondary">-</Text>,
    },
    {
      title: '操作',
      key: 'action',
      width: 100,
      render: (_, record) => (
        <Space>
          <Button
            type="text"
            size="small"
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
          />
          <Popconfirm
            title="确定删除这个单词吗？"
            onConfirm={() => handleDelete(record.id)}
            okText="删除"
            cancelText="取消"
          >
            <Button
              type="text"
              size="small"
              danger
              icon={<DeleteOutlined />}
            />
          </Popconfirm>
        </Space>
      ),
    },
  ]

  // 行选择配置
  const rowSelection = {
    selectedRowKeys,
    onChange: (newSelectedRowKeys: React.Key[]) => {
      setSelectedRowKeys(newSelectedRowKeys)
    },
  }

  return (
    <div style={{ padding: 0 }}>
      {/* 统计卡片 */}
      {stats && (
        <Card style={{ marginBottom: 16 }}>
          <Row gutter={24}>
            <Col span={6}>
              <Statistic
                title="总单词数"
                value={stats.total}
                prefix={<BookOutlined />}
              />
            </Col>
            <Col span={6}>
              <Statistic
                title="唯一单词数"
                value={stats.unique_words}
                suffix="个"
              />
            </Col>
            <Col span={6}>
              <Statistic
                title="人教版"
                value={stats.by_publisher['人教版'] || 0}
                valueStyle={{ color: '#52c41a' }}
              />
            </Col>
            <Col span={6}>
              <Statistic
                title="外研版"
                value={stats.by_publisher['外研版'] || 0}
                valueStyle={{ color: '#fa8c16' }}
              />
            </Col>
          </Row>
        </Card>
      )}

      {/* 筛选区域 */}
      <Card style={{ marginBottom: 16 }}>
        <Row gutter={16} align="middle">
          <Col>
            <Space>
              <Text type="secondary">筛选:</Text>
              <Select
                placeholder="出版社"
                allowClear
                style={{ width: 100 }}
                value={publisher}
                onChange={setPublisher}
                options={PUBLISHER_OPTIONS}
              />
              <Select
                placeholder="年级"
                allowClear
                style={{ width: 100 }}
                value={grade}
                onChange={setGrade}
                options={GRADE_OPTIONS}
              />
              <Select
                placeholder="学期"
                allowClear
                style={{ width: 100 }}
                value={semester}
                onChange={setSemester}
                options={SEMESTER_OPTIONS}
              />
            </Space>
          </Col>
          <Col>
            <Search
              placeholder="搜索单词或释义..."
              allowClear
              style={{ width: 250 }}
              onSearch={handleSearch}
              enterButton={<SearchOutlined />}
            />
          </Col>
          <Col>
            <Button icon={<ReloadOutlined />} onClick={handleReset}>
              重置
            </Button>
          </Col>
          <Col flex="auto" />
          <Col>
            <Space>
              {selectedRowKeys.length > 0 && (
                <Popconfirm
                  title={`确定删除选中的 ${selectedRowKeys.length} 个单词吗？`}
                  onConfirm={handleBatchDelete}
                  okText="删除"
                  cancelText="取消"
                >
                  <Button danger icon={<DeleteOutlined />}>
                    批量删除 ({selectedRowKeys.length})
                  </Button>
                </Popconfirm>
              )}
              <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>
                添加单词
              </Button>
            </Space>
          </Col>
        </Row>
      </Card>

      {/* 单词列表 */}
      <Card>
        <Table
          columns={columns}
          dataSource={vocabList}
          rowKey="id"
          loading={loading}
          rowSelection={rowSelection}
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: true,
            showQuickJumper: true,
            pageSizeOptions: ['20', '50', '100'],
            showTotal: (total) => `共 ${total} 个单词`,
            onChange: (p, ps) => {
              setPage(p)
              setPageSize(ps)
            },
          }}
        />
      </Card>

      {/* 新增/编辑弹窗 */}
      <Modal
        title={editingVocab ? '编辑单词' : '添加单词'}
        open={modalOpen}
        onOk={handleSave}
        onCancel={() => setModalOpen(false)}
        width={500}
      >
        <Form form={form} layout="vertical">
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="word"
                label="单词"
                rules={[{ required: true, message: '请输入单词' }]}
              >
                <Input placeholder="输入英文单词" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="pos" label="词性">
                <Input placeholder="如 n., v., adj." />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item
            name="definition"
            label="释义"
            rules={[{ required: true, message: '请输入释义' }]}
          >
            <Input.TextArea rows={2} placeholder="输入中文释义" />
          </Form.Item>
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item
                name="publisher"
                label="出版社"
                rules={[{ required: true, message: '请选择出版社' }]}
              >
                <Select options={PUBLISHER_OPTIONS} placeholder="选择出版社" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item
                name="grade"
                label="年级"
                rules={[{ required: true, message: '请选择年级' }]}
              >
                <Select options={GRADE_OPTIONS} placeholder="选择年级" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item
                name="semester"
                label="学期"
                rules={[{ required: true, message: '请选择学期' }]}
              >
                <Select options={SEMESTER_OPTIONS} placeholder="选择学期" />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="unit" label="单元">
            <Input placeholder="如 Unit 1, Module 4" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
