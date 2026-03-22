/**
 * 作文讲义视图容器组件
 *
 * [INPUT]: 依赖 antd、GradeWritingHandout
 * [OUTPUT]: 对外提供 WritingHandoutView 组件
 * [POS]: frontend/src/components/writingHandout 的讲义视图容器
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */
import { useState, useEffect } from 'react'
import { Row, Col, Card, Radio, Typography, Space, Tag, Spin, Empty } from 'antd'
import { BookOutlined } from '@ant-design/icons'

import { GradeWritingHandout } from './GradeWritingHandout'
import { getWritingFilters } from '@/services/writingService'

const { Title, Text } = Typography

// 年级颜色映射
const GRADE_COLORS: Record<string, string> = {
  '初一': '#1890ff',
  '初二': '#52c41a',
  '初三': '#722ed1',
}

// ============================================================================
//  主组件
// ============================================================================

export function WritingHandoutView() {
  const [selectedGrade, setSelectedGrade] = useState<string | null>(null)
  const [edition, setEdition] = useState<'teacher' | 'student'>('teacher')
  const [availableGrades, setAvailableGrades] = useState<string[]>([])
  const [loading, setLoading] = useState(true)

  // 加载可用的年级
  useEffect(() => {
    loadAvailableGrades()
  }, [])

  const loadAvailableGrades = async () => {
    try {
      setLoading(true)
      const filters = await getWritingFilters()
      setAvailableGrades(filters.grades || [])
    } catch (error) {
      console.error('加载年级列表失败:', error)
    } finally {
      setLoading(false)
    }
  }

  // 如果已选择年级，显示讲义内容
  if (selectedGrade) {
    return (
      <GradeWritingHandout
        grade={selectedGrade}
        edition={edition}
        onBack={() => setSelectedGrade(null)}
      />
    )
  }

  // 加载中
  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 48 }}>
        <Spin size="large" tip="加载年级数据..." />
      </div>
    )
  }

  // 没有数据
  if (availableGrades.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: 48 }}>
        <Empty description="暂无作文数据，请先导入作文题目" />
      </div>
    )
  }

  // 年级选择界面
  return (
    <div style={{ padding: 24 }}>
      {/* 版本切换器 */}
      <div style={{ marginBottom: 24, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Title level={3} style={{ margin: 0 }}>
          <BookOutlined style={{ marginRight: 8 }} />
          作文讲义
        </Title>
        <Radio.Group
          value={edition}
          onChange={(e) => setEdition(e.target.value)}
          buttonStyle="solid"
        >
          <Radio.Button value="teacher">教师版</Radio.Button>
          <Radio.Button value="student">学生版</Radio.Button>
        </Radio.Group>
      </div>

      {/* 说明 */}
      <Card style={{ marginBottom: 24 }}>
        <Space direction="vertical">
          <Text>作文讲义按<strong>话题分类</strong>，采用<strong>四段式结构</strong>：</Text>
          <ul style={{ margin: 0, paddingLeft: 20 }}>
            <li><Text>话题目录 - 统计各话题的题目数量和考查年份</Text></li>
            <li><Text>写作框架 - 标准结构模板（开头句、背景句、中心句、主体段、结尾句）</Text></li>
            <li><Text>高频表达 - 开头句型、结尾句型、过渡词汇、高级词汇</Text></li>
            <li><Text>范文展示 - 真题范文 + 重点句标注（教师版含解析）</Text></li>
          </ul>
        </Space>
      </Card>

      {/* 年级选择 - 只显示有数据的年级 */}
      <Title level={4}>选择年级</Title>
      <Row gutter={[16, 16]}>
        {availableGrades.map((grade) => (
          <Col xs={24} sm={12} md={8} key={grade}>
            <Card
              hoverable
              onClick={() => setSelectedGrade(grade)}
              style={{
                textAlign: 'center',
                cursor: 'pointer',
                borderLeft: `4px solid ${GRADE_COLORS[grade] || '#999'}`,
              }}
            >
              <Title level={2} style={{ margin: 0, color: GRADE_COLORS[grade] || '#999' }}>
                {grade}
              </Title>
              <Text type="secondary">作文讲义</Text>
            </Card>
          </Col>
        ))}
      </Row>

      {/* 当前版本提示 */}
      <div style={{ marginTop: 24, textAlign: 'center' }}>
        <Tag color={edition === 'teacher' ? 'blue' : 'green'}>
          当前：{edition === 'teacher' ? '教师版（含重点句解析）' : '学生版'}
        </Tag>
      </div>
    </div>
  )
}
