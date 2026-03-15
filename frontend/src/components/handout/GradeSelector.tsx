/**
 * 年级选择器组件
 *
 * [INPUT]: 依赖 antd
 * [OUTPUT]: 对外提供 GradeSelector 组件
 * [POS]: frontend/src/components/handout 的年级选择器
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */
import { Card, Row, Col, Typography, Spin, Empty } from 'antd'
import { BookOutlined } from '@ant-design/icons'

const { Title, Text } = Typography

interface GradeSelectorProps {
  grades: string[]          // 年级列表
  title?: string            // 标题后缀（如 "阅读 CD篇" 或 "完形填空"）
  loading?: boolean         // 加载状态
  onSelect: (grade: string) => void
}

interface GradeInfo {
  grade: string
  icon: string
}

export function GradeSelector({ grades, title = '', loading = false, onSelect }: GradeSelectorProps) {
  const getGradeIcon = (grade: string): string => {
    if (grade.includes('初三') || grade.includes('中考')) return '🎓'
    if (grade.includes('初二')) return '📚'
    if (grade.includes('初一')) return '📖'
    return '📓'
  }

  // 将年级列表转换为带图标的格式
  const gradeData: GradeInfo[] = grades.map(grade => ({
    grade,
    icon: getGradeIcon(grade),
  }))

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 48 }}>
        <Spin size="large" />
        <div style={{ marginTop: 16 }}>
          <Text type="secondary">加载年级列表...</Text>
        </div>
      </div>
    )
  }

  if (grades.length === 0) {
    return (
      <Empty description="暂无年级数据" />
    )
  }

  return (
    <div>
      <Title level={3} style={{ marginBottom: 24, textAlign: 'center' }}>
        <BookOutlined /> 选择年级
      </Title>

      <Row gutter={[16, 16]}>
        {gradeData.map(g => (
          <Col xs={24} sm={12} md={8} lg={6} key={g.grade}>
            <Card
              hoverable
              onClick={() => onSelect(g.grade)}
              style={{
                textAlign: 'center',
                cursor: 'pointer',
                transition: 'all 0.3s',
              }}
              styles={{
                body: {
                  padding: '24px 16px',
                },
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.transform = 'translateY(-4px)'
                e.currentTarget.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.15)'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = 'translateY(0)'
                e.currentTarget.style.boxShadow = 'none'
              }}
            >
              <div style={{ fontSize: 48, marginBottom: 12 }}>
                {g.icon}
              </div>
              <Title level={4} style={{ marginBottom: 8 }}>
                {g.grade}{title}
              </Title>
              <Text type="secondary">
                点击查看讲义
              </Text>
            </Card>
          </Col>
        ))}
      </Row>
    </div>
  )
}
