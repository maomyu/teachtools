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
import { Typography, Divider, Tag, Space, Table } from 'antd'
import type { ClozeHandoutPassage, ClozePoint } from '@/types'
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

      {/* 详细解析页（仅教师版） */}
      {edition === 'teacher' && points && points.length > 0 && (
        <ClozeExplanationPages points={points} sourceText={sourceText} />
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

// ============================================================================
//  子组件：教师版详细解析页
// ============================================================================

interface ClozeExplanationPagesProps {
  points: ClozePoint[]
  sourceText: string
}

function ClozeExplanationPages({ points, sourceText }: ClozeExplanationPagesProps) {
  // 每页显示 1 个解析
  const ITEMS_PER_PAGE = 1
  const pages: ClozePoint[][] = []
  for (let i = 0; i < points.length; i += ITEMS_PER_PAGE) {
    pages.push(points.slice(i, i + ITEMS_PER_PAGE))
  }

  return (
    <>
      {pages.map((pagePoints, pageIdx) => (
        <section key={`explanation-${pageIdx}`} className="handout-page part-page">
          {pageIdx === 0 ? (
            <>
              <Title level={3}>答案解析</Title>
              <div style={{ marginBottom: 8 }}>
                <Text type="secondary">{sourceText}</Text>
              </div>
              <Divider style={{ margin: '12px 0' }} />
            </>
          ) : (
            <>
              <Title level={4}>答案解析（续 {pageIdx + 1}）</Title>
              <Divider style={{ margin: '12px 0' }} />
            </>
          )}

          {pagePoints.map((point, idx) => (
            <PointExplanationCard
              key={point.id || idx}
              point={point}
            />
          ))}
        </section>
      ))}
    </>
  )
}

// ============================================================================
//  单个考点解析卡片
// ============================================================================

interface PointExplanationCardProps {
  point: ClozePoint
}

function PointExplanationCard({ point }: PointExplanationCardProps) {
  const correctWord = point.correct_word || point.correct_answer || '-'

  // 构建选项数据：选项词 + 排除理由
  const optionData = buildOptionData(point, correctWord)

  return (
    <div style={{
      marginBottom: 16,
      padding: 12,
      border: '1px solid #e8e8e8',
      borderRadius: 4,
      background: '#fafafa'
    }}>
      {/* 标题行：题号 + 正确答案 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
        <Tag color="blue" style={{ fontSize: '12pt', padding: '2px 8px' }}>
          {point.blank_number}.
        </Tag>
        <Text strong style={{ fontSize: '13pt' }}>{correctWord}</Text>
      </div>

      {/* 1. 选项表格：选项词 + 排除理由 */}
      <Table
        dataSource={optionData}
        size="small"
        pagination={false}
        bordered
        tableLayout="fixed"
        style={{ width: '100%', marginBottom: 12 }}
        columns={[
          {
            title: '选项',
            dataIndex: 'option',
            key: 'option',
            width: 60,
            align: 'center',
            render: (opt: string) => <Text strong>{opt}</Text>
          },
          {
            title: '选项词',
            dataIndex: 'word',
            key: 'word',
            width: 80,
            align: 'center',
            render: (word: string, record: OptionRow) => (
              <Text type={record.isCorrect ? 'success' : undefined} strong={record.isCorrect}>
                {word}
              </Text>
            )
          },
          {
            title: '排除理由',
            dataIndex: 'rejection_reason',
            key: 'rejection_reason',
            render: (reason: string, record: OptionRow) => (
              <Text type={record.isCorrect ? 'success' : 'secondary'} style={{ fontSize: '10pt' }}>
                {record.isCorrect ? '正确答案' : (reason || '-')}
              </Text>
            )
          }
        ]}
      />

      {/* 2. 解析 */}
      {point.explanation && (
        <div style={{ marginBottom: 8 }}>
          <Text type="secondary" style={{ fontSize: '11pt' }}>解析：</Text>
          <Text style={{ fontSize: '11pt' }}>{point.explanation}</Text>
        </div>
      )}

      {/* 3. 解题技巧 */}
      {point.tips && (
        <div style={{
          marginTop: 8,
          padding: '8px 12px',
          background: '#e6f7ff',
          borderRadius: 4,
          borderLeft: '3px solid #1890ff'
        }}>
          <Text type="secondary" style={{ fontSize: '11pt' }}>解题技巧：</Text>
          <Text style={{ fontSize: '11pt', marginLeft: 4 }}>{point.tips}</Text>
        </div>
      )}
    </div>
  )
}

// ============================================================================
//  辅助函数：构建选项数据（选项词 + 排除理由）
// ============================================================================

interface OptionRow {
  key: string
  option: string          // A/B/C/D
  word: string            // 选项词
  rejection_reason: string // 排除理由
  isCorrect: boolean      // 是否正确答案
}

function buildOptionData(point: ClozePoint, correctWord: string): OptionRow[] {
  const options = point.options || {}
  const wordAnalysis = point.word_analysis || {}
  const rejectionPoints = point.rejection_points || []

  // 构建排错点映射：option_word -> explanation + point_code
  const rejectionMap = new Map<string, string>()
  rejectionPoints.forEach(rp => {
    const reason = rp.explanation
      ? `${rp.point_code ? `[${rp.point_code}] ` : ''}${rp.explanation}`
      : rp.point_code || ''
    rejectionMap.set(rp.option_word, reason)
  })

  const optionKeys = ['A', 'B', 'C', 'D'] as const

  return optionKeys.map(opt => {
    const word = options[opt] || '-'
    const isCorrect = word === correctWord

    // 优先从 rejection_points 获取，否则从 word_analysis 获取
    let rejectionReason = rejectionMap.get(word) || ''
    if (!rejectionReason && wordAnalysis) {
      const analysis = wordAnalysis[word] as { rejection_reason?: string } | undefined
      rejectionReason = analysis?.rejection_reason || ''
    }

    return {
      key: opt,
      option: opt,
      word,
      rejection_reason: rejectionReason,
      isCorrect
    }
  })
}
