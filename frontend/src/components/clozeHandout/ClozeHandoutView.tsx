/**
 * 完形填空讲义视图容器
 *
 * [INPUT]: 依赖 antd, clozeService
 * [OUTPUT]: 对外提供 ClozeHandoutView 组件
 * [POS]: frontend/src/components/clozeHandout 的入口组件
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */
import { useState, useEffect } from 'react'
import { Radio, Space } from 'antd'
import { GradeSelector } from '@/components/handout/GradeSelector'
import { ClozeGradeHandout } from './ClozeGradeHandout'
import { getClozeFilters } from '@/services/clozeService'

export function ClozeHandoutView() {
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
      const filters = await getClozeFilters()
      setGrades(filters.grades)
    } catch (error) {
      console.error('加载年级失败:', error)
    } finally {
      setLoadingGrades(false)
    }
  }

  return (
    <div>
      {/* 版本切换（在年级选择后显示） */}
      {selectedGrade && (
        <div style={{ marginBottom: 16 }}>
          <Space>
            <span>版本：</span>
            <Radio.Group
              value={edition}
              onChange={(e) => setEdition(e.target.value)}
              optionType="button"
              buttonStyle="solid"
            >
              <Radio.Button value="teacher">教师版</Radio.Button>
              <Radio.Button value="student">学生版</Radio.Button>
            </Radio.Group>
          </Space>
        </div>
      )}

      {/* 年级选择或讲义内容 */}
      {!selectedGrade ? (
        <GradeSelector
          grades={grades}
          loading={loadingGrades}
          title="完形填空"
          onSelect={setSelectedGrade}
        />
      ) : (
        <ClozeGradeHandout
          grade={selectedGrade}
          edition={edition}
          onBack={() => setSelectedGrade(null)}
        />
      )}
    </div>
  )
}
