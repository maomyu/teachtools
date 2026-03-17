/**
 * 完形文章展示组件
 *
 * [INPUT]: 依赖 antd, types
 * [OUTPUT]: 对外提供 ClozePassagePages 组件
 * [POS]: frontend/src/components/clozeHandout 的文章展示
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 *
 * V2 更新：使用 CATEGORY_COLORS 替代旧的 POINT_TYPE_COLORS
 */
import { Typography, Divider, Tag, Space } from 'antd'
import type { ClozeHandoutPassage } from '@/types'
import { CATEGORY_COLORS, LEGACY_TO_NEW_CODE } from '@/types'

const { Title, Text } = Typography

// ============================================================================
//  辅助函数：获取考点颜色
// ============================================================================

/**
 * 根据考点类型获取颜色
 * 支持 V2 编码（如 A1, C2）和旧类型（如 固定搭配）
 */
function getPointColor(pointType?: string): string {
  if (!pointType) return 'default'

  // 如果是 V2 编码（如 A1, B2），直接从第一个字符获取大类
  if (/^[A-E]\d/.test(pointType)) {
    const category = pointType[0]
    return CATEGORY_COLORS[category] || 'default'
  }

  // 如果是旧类型，先映射到 V2 编码
  const v2Code = LEGACY_TO_NEW_CODE[pointType]
  if (v2Code) {
    const category = v2Code[0]
    return CATEGORY_COLORS[category] || 'default'
  }

  return 'default'
}

// ============================================================================
//  Props 定义
// ============================================================================

interface ClozePassagePagesProps {
  passage: ClozeHandoutPassage
  edition: 'teacher' | 'student'
  index: number
  total: number
}

// ============================================================================
//  主组件：完形文章展示
// ============================================================================

export function ClozePassagePages({ passage, edition, index, total }: ClozePassagePagesProps) {
  const { content, word_count, source, points } = passage

  // 构建来源文本
  const sourceText = source
    ? `${source.year} ${source.region} ${source.exam_type || ''}`
    : '来源未知'

  return (
    <>
      {/* 文章正文页 */}
      <section className="handout-page part-page">
        <Title level={3} style={{ marginBottom: 8 }}>
          四、完形文章（{index + 1}/{total}）
        </Title>
        <div className="passage-header" style={{ marginBottom: 8 }}>
          <Space size="middle">
            <Text type="secondary">{sourceText}</Text>
            {word_count && (
              <Text type="secondary">词数：{word_count}</Text>
            )}
          </Space>
        </div>
        <Divider style={{ margin: '12px 0' }} />

        {/* 文章正文 */}
        <div className="passage-body" style={{ lineHeight: 2, fontSize: '11pt' }}>
          <ClozeContent content={content} points={points} />
        </div>
      </section>

      {/* 选项页（所有空格的选项在一页） */}
      {points && points.length > 0 && (
        <section className="handout-page part-page">
          <Title level={3}>选项词</Title>
          <div style={{ marginBottom: 8 }}>
            <Text type="secondary">{sourceText}</Text>
          </div>
          <Divider style={{ margin: '12px 0' }} />

          {/* 选项表格 */}
          <table className="options-table" style={{
            width: '100%',
            borderCollapse: 'collapse',
            fontSize: '11pt',
            tableLayout: 'fixed'
          }}>
            <thead>
              <tr>
                <th style={{
                  width: '20%',
                  border: '1px solid #d9d9d9',
                  padding: '10px 12px',
                  background: '#f5f5f5',
                  textAlign: 'center'
                }}>
                  题号
                </th>
                <th style={{
                  width: '20%',
                  border: '1px solid #d9d9d9',
                  padding: '10px 12px',
                  background: '#f5f5f5',
                  textAlign: 'center'
                }}>
                  A
                </th>
                <th style={{
                  width: '20%',
                  border: '1px solid #d9d9d9',
                  padding: '10px 12px',
                  background: '#f5f5f5',
                  textAlign: 'center'
                }}>
                  B
                </th>
                <th style={{
                  width: '20%',
                  border: '1px solid #d9d9d9',
                  padding: '10px 12px',
                  background: '#f5f5f5',
                  textAlign: 'center'
                }}>
                  C
                </th>
                <th style={{
                  width: '20%',
                  border: '1px solid #d9d9d9',
                  padding: '10px 12px',
                  background: '#f5f5f5',
                  textAlign: 'center'
                }}>
                  D
                </th>
              </tr>
            </thead>
            <tbody>
              {points.map((point, idx) => (
                <tr key={point.id || idx}>
                  <td style={{
                    border: '1px solid #d9d9d9',
                    padding: '10px 12px',
                    textAlign: 'center',
                    fontWeight: 'bold'
                  }}>
                    {point.blank_number}
                  </td>
                  <td style={{
                    border: '1px solid #d9d9d9',
                    padding: '10px 12px',
                    textAlign: 'center'
                  }}>
                    {point.options?.A || '-'}
                  </td>
                  <td style={{
                    border: '1px solid #d9d9d9',
                    padding: '10px 12px',
                    textAlign: 'center'
                  }}>
                    {point.options?.B || '-'}
                  </td>
                  <td style={{
                    border: '1px solid #d9d9d9',
                    padding: '10px 12px',
                    textAlign: 'center'
                  }}>
                    {point.options?.C || '-'}
                  </td>
                  <td style={{
                    border: '1px solid #d9d9d9',
                    padding: '10px 12px',
                    textAlign: 'center'
                  }}>
                    {point.options?.D || '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {/* 答案页（仅教师版） */}
      {edition === 'teacher' && points && points.length > 0 && (
        <section className="handout-page part-page">
          <Title level={3}>参考答案</Title>
          <Divider style={{ margin: '12px 0' }} />
          <div style={{ lineHeight: 2.5, fontSize: '12pt' }}>
            {points.map((point, idx) => (
              <Text key={point.id || idx} style={{ marginRight: 32, fontSize: '12pt' }}>
                {point.blank_number}. <Text strong>{point.correct_word || point.correct_answer}</Text>
              </Text>
            ))}
          </div>
        </section>
      )}
    </>
  )
}

// ============================================================================
//  子组件：完形内容渲染（带空格标记）
// ============================================================================

interface ClozeContentProps {
  content: string
  points: ClozeHandoutPassage['points']
}

function ClozeContent({ content, points }: ClozeContentProps) {
  // 将原文中的 (数字) 替换为空格标记
  const parts = content.split(/\((\d+)\)/g)

  return (
    <div style={{ textIndent: '2em' }}>
      {parts.map((part, idx) => {
        // 检查是否是空格标记
        if (/^\d+$/.test(part)) {
          const blankNum = parseInt(part)
          const point = points?.find(p => p.blank_number === blankNum)
          const pointType = point?.point_type || ''

          return (
            <Tag
              key={idx}
              color={getPointColor(pointType)}
              style={{ margin: '0 2px', fontSize: '10pt' }}
            >
              [{blankNum}]
            </Tag>
          )
        }
        // 普通文本
        return <span key={idx}>{part}</span>
      })}
    </div>
  )
}
