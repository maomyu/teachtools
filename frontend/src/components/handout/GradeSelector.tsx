/**
 * 年级选择器组件
 *
 * [INPUT]: 依赖 antd、readingService
 * [OUTPUT]: 对外提供 GradeSelector 组件
 * [POS]: frontend/src/components/handout 的年级选择器
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */
import { useState, useEffect } from 'react'
import { Card, Row, Col, Typography, Spin, Empty } from 'antd'
import { BookOutlined } from '@ant-design/icons'

import { getPassageFilters } from '@/services/readingService'

const { Title, Text } = Typography

interface GradeSelectorProps {
  onSelect: (grade: string) => void
}

interface GradeInfo {
  grade: string
  icon: string
  count: number
}

export function GradeSelector({ onSelect }: GradeSelectorProps) {
  const [grades, setGrades] = useState<GradeInfo[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadGrades()
  }, [])

  const loadGrades = async () => {
    try {
      setLoading(true)
      // 获取筛选项（包含年级列表）
      const filters = await getPassageFilters()

      // 为每个年级设置图标和初始计数
      const gradeData: GradeInfo[] = filters.grades.map(grade => ({
        grade,
        icon: getGradeIcon(grade),
        count: 0, // 暂时设为0，实际应该调用统计API
      }))

      setGrades(gradeData)
    } catch (error) {
      console.error('加载年级失败:', error)
    } finally {
      setLoading(false)
    }
  }

  const getGradeIcon = (grade: string): string => {
    if (grade.includes('初三') || grade.includes('中考')) return '🎓'
    if (grade.includes('初二')) return '📚'
    if (grade.includes('初一')) return '📖'
    return '📓'
  }

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
        {grades.map(g => (
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
                {g.grade}阅读 CD篇
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
