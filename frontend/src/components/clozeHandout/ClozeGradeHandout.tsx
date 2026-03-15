/**
 * 完形年级讲义组件（A4 文档格式）
 *
 * [INPUT]: 依赖 antd, clozeService, pdfExport
 * [OUTPUT]: 对外提供 ClozeGradeHandout 组件
 * [POS]: frontend/src/components/clozeHandout 的年级讲义主组件
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */
import { useState, useEffect, useRef } from 'react'
import {
  Button,
  Space,
  Tag,
  Typography,
  Spin,
  Empty,
} from 'antd'
import {
  ArrowLeftOutlined,
  DownloadOutlined,
} from '@ant-design/icons'

import { getClozeGradeHandout } from '@/services/clozeService'
import { exportToPDF } from '@/utils/pdfExport'
import type {
  ClozeGradeHandoutResponse,
} from '@/types'
import { ClozeTopicSection } from './ClozeTopicSection'
import '@/components/handout/HandoutDetail.css'
import './ClozeHandout.css'

const { Title, Text } = Typography

// ============================================================================
//  Props 定义
// ============================================================================

interface ClozeGradeHandoutProps {
  grade: string
  edition: 'teacher' | 'student'
  onBack: () => void
}

// ============================================================================
//  主组件：完形年级讲义（A4 文档）
// ============================================================================

export function ClozeGradeHandout({ grade, edition, onBack }: ClozeGradeHandoutProps) {
  const [handout, setHandout] = useState<ClozeGradeHandoutResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [exporting, setExporting] = useState(false)
  const contentRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    loadHandout()
  }, [grade, edition])

  const loadHandout = async () => {
    try {
      setLoading(true)
      const response = await getClozeGradeHandout(grade, edition)
      setHandout(response)
    } catch (error) {
      console.error('加载讲义失败:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleExport = async () => {
    if (!contentRef.current) return
    try {
      setExporting(true)
      const filename = `${grade}完形填空讲义_${edition === 'teacher' ? '教师版' : '学生版'}_${new Date().toLocaleDateString('zh-CN').replace(/\//g, '-')}`
      await exportToPDF(contentRef.current, filename)
    } finally {
      setExporting(false)
    }
  }

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 48 }}>
        <Spin size="large" />
        <div style={{ marginTop: 16 }}>
          <Text type="secondary">加载讲义内容...</Text>
        </div>
      </div>
    )
  }

  if (!handout) {
    return <Empty description="讲义内容不存在" />
  }

  return (
    <div className="handout-container">
      {/* 操作栏 */}
      <div className="handout-toolbar no-print">
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={onBack}>
            返回年级选择
          </Button>
          <Button
            type="primary"
            icon={<DownloadOutlined />}
            loading={exporting}
            onClick={handleExport}
          >
            下载 PDF
          </Button>
        </Space>
        <Tag color={edition === 'teacher' ? 'blue' : 'green'} style={{ fontSize: 14, padding: '4px 12px' }}>
          {edition === 'teacher' ? '教师版' : '学生版'}
        </Tag>
      </div>

      {/* A4 文档内容 */}
      <div ref={contentRef} className="handout-pages">
        {/* 封面页 */}
        <section className="handout-page cover-page">
          <div className="cover-content">
            <Title level={1} style={{ marginBottom: 24 }}>{grade}完形填空讲义</Title>
            <div style={{ marginTop: 48 }}>
              <Text style={{ fontSize: 18, display: 'block', marginBottom: 16 }}>
                {edition === 'teacher' ? '教师版（含答案和解析）' : '学生版'}
              </Text>
              <Text type="secondary" style={{ fontSize: 14 }}>
                生成日期：{new Date().toLocaleDateString('zh-CN')}
              </Text>
            </div>
          </div>
        </section>

        {/* 目录页 */}
        <section className="handout-page toc-page">
          <Title level={2} style={{ marginBottom: 32 }}>目 录</Title>
          <div className="toc-list">
            {handout.topics.map((t, idx) => (
              <div key={t.topic} className="toc-item" style={{
                display: 'flex',
                justifyContent: 'space-between',
                padding: '12px 0',
                borderBottom: '1px dashed #e8e8e8'
              }}>
                <Text style={{ fontSize: 16 }}>
                  {idx + 1}. {t.topic}
                </Text>
                <Text type="secondary" style={{ fontSize: 14 }}>
                  {t.passage_count} 篇文章
                </Text>
              </div>
            ))}
          </div>
        </section>

        {/* 每个主题的内容 */}
        {handout.content.map((topicContent, topicIdx) => (
          <ClozeTopicSection
            key={topicContent.topic}
            topicContent={topicContent}
            edition={edition}
            topicIndex={topicIdx + 1}
          />
        ))}
      </div>
    </div>
  )
}
