/**
 * 讲义视图容器组件
 *
 * [INPUT]: 依赖 GradeSelector、GradeHandout
 * [OUTPUT]: 对外提供 HandoutView 组件
 * [POS]: frontend/src/components/handout 的讲义视图容器
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */
import { useState, useEffect } from 'react'
import { Radio, Typography, Space } from 'antd'

import { GradeSelector } from './GradeSelector'
import { GradeHandout } from './GradeHandout'
import { getPassageFilters } from '@/services/readingService'

const { Text } = Typography

export function HandoutView() {
  const [selectedGrade, setSelectedGrade] = useState<string | null>(null)
  const [edition, setEdition] = useState<'teacher' | 'student'>('teacher')
  const [grades, setGrades] = useState<string[]>([])
  const [loadingGrades, setLoadingGrades] = useState(true)

  // 加载年级列表
  useEffect(() => {
    loadGrades()
  }, [])

  const loadGrades = async () => {
    try {
      setLoadingGrades(true)
      const filters = await getPassageFilters()
      setGrades(filters.grades)
    } catch (error) {
      console.error('加载年级失败:', error)
    } finally {
      setLoadingGrades(false)
    }
  }

  return (
    <div style={{ padding: 24, height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* 版本切换器 */}
      {selectedGrade && (
        <div
          style={{
            marginBottom: 16,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <Space>
            <Text strong style={{ fontSize: 16 }}>
              当前年级：{selectedGrade}
            </Text>
          </Space>

          <Radio.Group
            value={edition}
            onChange={(e) => setEdition(e.target.value)}
            buttonStyle="solid"
          >
            <Radio.Button value="teacher">教师版</Radio.Button>
            <Radio.Button value="student">学生版</Radio.Button>
          </Radio.Group>
        </div>
      )}

      {/* 内容区域 */}
      <div style={{ flex: 1, overflow: 'auto' }}>
        {/* 年级选择 */}
        {!selectedGrade && (
          <GradeSelector
            grades={grades}
            loading={loadingGrades}
            title="阅读 CD篇"
            onSelect={setSelectedGrade}
          />
        )}

        {/* 年级讲义 */}
        {selectedGrade && (
          <GradeHandout
            grade={selectedGrade}
            edition={edition}
            onBack={() => setSelectedGrade(null)}
          />
        )}
      </div>
    </div>
  )
}
