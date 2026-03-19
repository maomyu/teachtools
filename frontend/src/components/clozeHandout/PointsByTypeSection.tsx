/**
 * 考点分类区块组件（V2 版本）
 *
 * [INPUT]: 依赖 antd, types, PointTag
 * [OUTPUT]: 对外提供 PointsByTypeSection 组件
 * [POS]: frontend/src/components/clozeHandout 的考点分类组件
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 *
 * V2 更新：
 * - 支持按 16 种考点编码分组（A1-E2）
 * - 使用 PointTag 组件显示考点标签
 * - 只展示有数据的考点类型
 */
import { Typography, Divider, Tag, Table } from 'antd'
import type { PointsByType, PointWordData } from '@/types'
import { CATEGORY_COLORS, CATEGORY_NAMES, ALL_POINT_TYPES, POINT_TYPE_BY_CODE } from '@/types'
import { PointTag } from '@/components/cloze/PointTag'

const { Title, Text } = Typography

// ============================================================================
//  Props 定义
// ============================================================================

interface PointsByTypeSectionProps {
  pointsByType: PointsByType
  edition: 'teacher' | 'student'
}

// ============================================================================
//  主组件：考点分类区块
// ============================================================================

export function PointsByTypeSection({ pointsByType, edition }: PointsByTypeSectionProps) {
  // 使用完整的 16 种考点类型列表（按顺序）
  const allPointCodes = ALL_POINT_TYPES.map(pt => pt.code)

  // 获取有数据的考点编码
  const codesWithData = allPointCodes.filter(code => {
    const group = pointsByType[code]
    return group && group.points && group.points.length > 0
  })

  // 判断是否有任何考点数据
  if (codesWithData.length === 0) {
    return (
      <section className="handout-page part-page">
        <Title level={3}>三、考点分类</Title>
        <Divider />
        <Text type="secondary">暂无考点分析数据</Text>
      </section>
    )
  }

  return (
    <>
      {/* 考点详细展示页（只展示有数据的类型） */}
      {codesWithData.map((code, idx) => {
        const group = pointsByType[code]
        const typeDef = POINT_TYPE_BY_CODE[code]

        return (
          <PointCodeSection
            key={code}
            code={code}
            name={group?.name || typeDef?.name || code}
            category={group?.category || code[0]}
            categoryName={group?.category_name || typeDef?.categoryName || CATEGORY_NAMES[code[0]]}
            points={group.points}
            edition={edition}
            showMainTitle={idx === 0}
          />
        )
      })}
    </>
  )
}

// ============================================================================
//  单个考点编码区块
// ============================================================================

interface PointCodeSectionProps {
  code: string
  name: string
  category: string
  categoryName: string
  points: PointWordData[]
  edition: 'teacher' | 'student'
  showMainTitle: boolean
}

function PointCodeSection({
  code,
  name,
  category,
  categoryName,
  points,
  edition,
  showMainTitle
}: PointCodeSectionProps) {
  const color = CATEGORY_COLORS[category] || 'default'
  const totalPoints = points.length

  // 根据考点类型选择展示方式
  // C2 (固定搭配) 使用通用组件，和其他考点一样显示 4 个选项词
  // D1 (词义辨析) 使用 WordAnalysisTable 风格
  // D2 (熟词僻义) 使用 RareMeaningSection 风格
  // 其他使用通用表格

  if (code === 'D1') {
    return <WordAnalysisStyleSection {...{ code, name, category, points, edition, showMainTitle, color, totalPoints }} />
  } else if (code === 'D2') {
    return <RareMeaningStyleSection {...{ code, name, category, points, edition, showMainTitle, color, totalPoints }} />
  } else {
    // C2 固定搭配和其他考点类型统一使用通用组件，显示 4 个选项词
    return <GenericPointSection {...{ code, name, category, categoryName, points, edition, showMainTitle, color, totalPoints }} />
  }
}

// ============================================================================
//  通用考点区块（用于 A1-A5, B1-B4, C1, C3, E1-E2 等）
// ============================================================================

interface BaseSectionProps {
  code: string
  name: string
  category: string
  categoryName?: string
  points: PointWordData[]
  edition: 'teacher' | 'student'
  showMainTitle: boolean
  color: string
  totalPoints: number
}

function GenericPointSection({
  code,
  name,
  category,
  categoryName,
  points,
  edition,
  showMainTitle,
  color,
  totalPoints
}: BaseSectionProps) {
  // 每页显示 1 个考点词（完整展示柯林斯词典表格）
  const MAX_PER_PAGE = 1
  const pages: PointWordData[][] = []
  for (let i = 0; i < points.length; i += MAX_PER_PAGE) {
    pages.push(points.slice(i, i + MAX_PER_PAGE))
  }

  return (
    <>
      {pages.map((pagePoints, pageIdx) => (
        <section key={`${code}-${pageIdx}`} className="handout-page part-page">
          {pageIdx === 0 ? (
            <>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
                <Title level={3} style={{ margin: 0 }}>
                  {showMainTitle ? `三、考点分类——${name}` : `考点分类——${name}`}
                </Title>
                <PointTag point={{ code, name, category }} size="m" />
                <Tag color={color}>{categoryName || CATEGORY_NAMES[category]} | 共 {totalPoints} 个</Tag>
              </div>
              <Divider />
            </>
          ) : (
            <>
              <Title level={4}>{name}（续 {pageIdx + 1}）</Title>
              <Divider />
            </>
          )}

          {/* 使用卡片式展示，每个卡片展示 4 个选项词 */}
          {pagePoints.map((point, idx) => (
            <GenericPointCard
              key={idx}
              point={point}
              edition={edition}
              index={pageIdx * MAX_PER_PAGE + idx}
              pointCode={code}
              pointName={name}
            />
          ))}
        </section>
      ))}
    </>
  )
}

// 通用考点卡片（展示 4 个选项词，不标注正确答案，不剧透答案）
function GenericPointCard({ point, index, pointCode, pointName }: { point: PointWordData; edition: string; index: number; pointCode?: string; pointName?: string }) {
  // 优先使用顶层 word_analysis，否则从第一个 occurrence 获取
  const wordAnalysis = point.word_analysis || point.occurrences?.[0]?.analysis?.word_analysis
  const optionWords = wordAnalysis ? Object.keys(wordAnalysis) : [point.word]
  const dictionarySource = point.dictionary_source || point.occurrences?.[0]?.analysis?.dictionary_source

  // V5: 动态提取维度列名（排除 rejection_reason，该字段应只在 rejection_points 中显示）
  const dimensionKeys: string[] = []
  optionWords.forEach(word => {
    const dims = wordAnalysis?.[word]?.dimensions
    if (dims) {
      Object.keys(dims).forEach(key => {
        // 过滤掉 rejection_reason，这是排错点的专用字段，不应作为通用维度列
        if (!dimensionKeys.includes(key) && key !== 'rejection_reason') {
          dimensionKeys.push(key)
        }
      })
    }
  })

  return (
    <div style={{ marginBottom: 20, padding: 12, border: '1px solid #d9d9d9', borderRadius: 4 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <Tag color="blue">{index + 1}</Tag>
        {pointCode && pointName && (
          <PointTag point={{ code: pointCode, name: pointName }} size="s" />
        )}
        {/* 不显示正确答案词和出现次数，避免剧透 */}
        {dictionarySource && (
          <Text type="secondary" style={{ fontSize: 12 }}>词典：{dictionarySource}</Text>
        )}
      </div>

      {/* V5 动态维度表格 */}
      {optionWords.length > 1 ? (
        <Table
          dataSource={optionWords.map(word => {
            // 过滤掉 rejection_reason 字段（应只在 rejection_points 中）
            const { rejection_reason: _, ...rest } = wordAnalysis?.[word] || {}
            return { key: word, word, ...rest }
          })}
          size="small"
          pagination={false}
          bordered
          tableLayout="fixed"
          style={{ width: '100%', maxWidth: '100%' }}
          columns={[
            {
              title: '选项词',
              dataIndex: 'word',
              key: 'word',
              width: 60,
              render: (word: string) => <Text>{word}</Text>
            },
            {
              title: '释义',
              dataIndex: 'definition',
              key: 'definition',
              width: 130,
              render: (def: string) => <div className="dimension-cell">{def || '-'}</div>
            },
            // V5: 动态维度列
            ...dimensionKeys.map(dimKey => ({
              title: dimKey,
              key: dimKey,
              width: 80,
              render: (_: unknown, record: { dimensions?: Record<string, string> }) => (
                <div className="dimension-cell">{record.dimensions?.[dimKey] || '-'}</div>
              )
            }))
          ]}
        />
      ) : (
        <div>
          <Text type="secondary">暂无选项词分析数据</Text>
        </div>
      )}
    </div>
  )
}

// ============================================================================
//  词义辨析风格区块（D1）
// ============================================================================

function WordAnalysisStyleSection(props: BaseSectionProps) {
  const { code, name, points, edition, showMainTitle, color, totalPoints } = props
  // 每页1个考点词（含4个选项词的三维度表格）
  const MAX_PER_PAGE = 1
  const pages: PointWordData[][] = []
  for (let i = 0; i < points.length; i += MAX_PER_PAGE) {
    pages.push(points.slice(i, i + MAX_PER_PAGE))
  }

  return (
    <>
      {pages.map((pagePoints, pageIdx) => (
        <section key={`${code}-${pageIdx}`} className="handout-page part-page">
          {pageIdx === 0 ? (
            <>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
                <Title level={3} style={{ margin: 0 }}>
                  {showMainTitle ? `三、考点分类——${name}` : `考点分类——${name}`}
                </Title>
                <PointTag point={{ code, name, category: props.category }} size="m" />
                <Tag color={color}>词汇选项类 | 共 {totalPoints} 个</Tag>
              </div>
              <Divider />
            </>
          ) : null}

          {pagePoints.map((point, idx) => (
            <WordAnalysisCard
              key={idx}
              point={point}
              edition={edition}
              index={pageIdx * MAX_PER_PAGE + idx}
              pointCode={code}
              pointName={name}
            />
          ))}
        </section>
      ))}
    </>
  )
}

// 词义辨析卡片（V5 动态维度）
function WordAnalysisCard({ point, index, pointCode, pointName }: { point: PointWordData; edition: string; index: number; pointCode?: string; pointName?: string }) {
  const analysis = point.word_analysis || {}
  const optionWords = Object.keys(analysis)

  // V5: 动态提取维度列名（排除 rejection_reason，该字段应只在 rejection_points 中显示）
  const dimensionKeys: string[] = []
  optionWords.forEach(word => {
    const dims = analysis[word]?.dimensions
    if (dims) {
      Object.keys(dims).forEach(key => {
        // 过滤掉 rejection_reason，这是排错点的专用字段，不应作为通用维度列
        if (!dimensionKeys.includes(key) && key !== 'rejection_reason') {
          dimensionKeys.push(key)
        }
      })
    }
  })

  return (
    <div style={{ marginBottom: 24 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <Tag color="orange">{index + 1}</Tag>
        {pointCode && pointName && (
          <PointTag point={{ code: pointCode, name: pointName }} size="s" />
        )}
        {/* 不显示正确答案词和出现次数，避免剧透 */}
      </div>

      {/* V5 动态维度表格 */}
      {optionWords.length > 0 && (
        <Table
          dataSource={optionWords.map(word => {
            // 过滤掉 rejection_reason 字段（应只在 rejection_points 中）
            const { rejection_reason: _, ...rest } = analysis[word] || {}
            return { key: word, word, ...rest }
          })}
          size="small"
          pagination={false}
          bordered
          tableLayout="fixed"
          style={{ width: '100%', maxWidth: '100%' }}
          columns={[
            {
              title: '选项词',
              dataIndex: 'word',
              key: 'word',
              width: 60,
              render: (word: string) => <Text>{word}</Text>
            },
            {
              title: '释义',
              dataIndex: 'definition',
              key: 'definition',
              width: 130,
              render: (def: string) => <div className="dimension-cell">{def || '-'}</div>
            },
            // V5: 动态维度列
            ...dimensionKeys.map(dimKey => ({
              title: dimKey,
              key: dimKey,
              width: 80,
              render: (_: unknown, record: { dimensions?: Record<string, string> }) => (
                <div className="dimension-cell">{record.dimensions?.[dimKey] || '-'}</div>
              )
            }))
          ]}
        />
      )}
    </div>
  )
}

// ============================================================================
//  固定搭配风格区块（C2）
// ============================================================================

function FixedPhraseStyleSection(props: BaseSectionProps) {
  const { code, name, points, showMainTitle, color, totalPoints } = props
  // 每页最多 6 个
  const MAX_PER_PAGE = 6
  const pages: PointWordData[][] = []
  for (let i = 0; i < points.length; i += MAX_PER_PAGE) {
    pages.push(points.slice(i, i + MAX_PER_PAGE))
  }

  return (
    <>
      {pages.map((pagePoints, pageIdx) => (
        <section key={`${code}-${pageIdx}`} className="handout-page part-page">
          {pageIdx === 0 ? (
            <>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
                <Title level={3} style={{ margin: 0 }}>
                  {showMainTitle ? `三、考点分类——${name}` : `考点分类——${name}`}
                </Title>
                <PointTag point={{ code, name, category: props.category }} size="m" />
                <Tag color={color}>句法语法类 | 共 {totalPoints} 个</Tag>
              </div>
              <Divider />
            </>
          ) : (
            <>
              <Title level={4}>{name}（续 {pageIdx + 1}）</Title>
              <Divider />
            </>
          )}

          <Table
            dataSource={pagePoints.map((p, idx) => ({ ...p, key: idx }))}
            size="small"
            pagination={false}
            bordered
            columns={[
              {
                title: '序号',
                key: 'index',
                width: 50,
                render: (_: unknown, __: PointWordData, idx: number) => pageIdx * MAX_PER_PAGE + idx + 1
              },
              {
                title: '考点词',
                dataIndex: 'word',
                key: 'word',
                width: 80,
                render: (word: string) => <Text strong>{word}</Text>
              },
              {
                title: '固定搭配',
                dataIndex: 'phrase',
                key: 'phrase',
                render: (phrase: string) => phrase ? <Text code>{phrase}</Text> : '-'
              },
              {
                title: '相似短语',
                dataIndex: 'similar_phrases',
                key: 'similar_phrases',
                render: (phrases: string[]) => phrases?.length ? phrases.join('、') : '-'
              },
              {
                title: '频次',
                dataIndex: 'frequency',
                key: 'frequency',
                width: 60,
                render: (freq: number) => <Tag>{freq}</Tag>
              }
              // 不展示解析 - 剧透答案，放在文章后面的答案解析中
            ]}
          />
        </section>
      ))}
    </>
  )
}

// ============================================================================
//  熟词僻义风格区块（D2）
// ============================================================================

function RareMeaningStyleSection(props: BaseSectionProps) {
  const { code, name, points, edition, showMainTitle, color, totalPoints } = props
  // 每页最多 4 个（有对比表格）
  const MAX_PER_PAGE = 4
  const pages: PointWordData[][] = []
  for (let i = 0; i < points.length; i += MAX_PER_PAGE) {
    pages.push(points.slice(i, i + MAX_PER_PAGE))
  }

  return (
    <>
      {pages.map((pagePoints, pageIdx) => (
        <section key={`${code}-${pageIdx}`} className="handout-page part-page">
          {pageIdx === 0 ? (
            <>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
                <Title level={3} style={{ margin: 0 }}>
                  {showMainTitle ? `三、考点分类——${name}` : `考点分类——${name}`}
                </Title>
                <PointTag point={{ code, name, category: props.category }} size="m" />
                <Tag color={color}>词汇选项类 | 共 {totalPoints} 个</Tag>
              </div>
              <Divider />
            </>
          ) : (
            <>
              <Title level={4}>{name}（续 {pageIdx + 1}）</Title>
              <Divider />
            </>
          )}

          {pagePoints.map((point, idx) => (
            <RareMeaningCard
              key={idx}
              point={point}
              edition={edition}
              index={pageIdx * MAX_PER_PAGE + idx}
              pointCode={code}
              pointName={name}
            />
          ))}
        </section>
      ))}
    </>
  )
}

// 熟词僻义卡片
function RareMeaningCard({ point, edition, index, pointCode, pointName }: { point: PointWordData; edition: string; index: number; pointCode?: string; pointName?: string }) {
  return (
    <div style={{ marginBottom: 20, padding: 12, border: '1px solid #d9d9d9', borderRadius: 4 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <Tag color="purple">{index + 1}</Tag>
        {pointCode && pointName && (
          <PointTag point={{ code: pointCode, name: pointName }} size="s" />
        )}
        {/* 不显示正确答案词和出现次数，避免剧透 */}
        {point.textbook_source && (
          <Tag>{point.textbook_source}</Tag>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div>
          <Text type="secondary">课本释义：</Text>
          <Text>{point.textbook_meaning || '-'}</Text>
        </div>
        <div>
          <Text type="secondary">语境释义：</Text>
          <Text strong>{point.context_meaning || '-'}</Text>
        </div>
      </div>

      {/* 英英定义（教师版） */}
      {edition === 'teacher' && point.word_analysis?.[point.word]?.definition && (
        <div style={{ marginTop: 8, padding: '8px 12px', background: '#fafafa', borderRadius: 4 }}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {point.dictionary_source || '柯林斯词典'}：
          </Text>
          <Text italic style={{ fontSize: 12, marginLeft: 4 }}>
            {point.word_analysis[point.word].definition}
          </Text>
        </div>
      )}

      {/* 相似熟词僻义 */}
      {point.similar_words && point.similar_words.length > 0 && (
        <div style={{ marginTop: 12 }}>
          <Text type="secondary">相似熟词僻义：</Text>
          <div style={{ marginTop: 4 }}>
            {point.similar_words.map((sw, idx) => (
              <Tag key={idx} style={{ marginBottom: 4 }}>
                {sw.word}：{sw.rare}
              </Tag>
            ))}
          </div>
        </div>
      )}
      {/* 不展示例句 - 剧透答案 */}
    </div>
  )
}
