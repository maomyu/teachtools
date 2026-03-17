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
 * - 按大类顺序展示（A → B → C → D → E）
 */
import { Typography, Divider, Tag, Table } from 'antd'
import type { PointsByType, PointWordData } from '@/types'
import { CATEGORY_COLORS, CATEGORY_NAMES } from '@/types'
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
  // 获取所有考点编码并排序
  const pointCodes = Object.keys(pointsByType).sort((a, b) => {
    // 按大类 (A-E) 和数字排序
    const categoryOrder = (c: string) => c.charCodeAt(0)
    const numOrder = (c: string) => parseInt(c.slice(1)) || 0
    const catA = categoryOrder(a), catB = categoryOrder(b)
    if (catA !== catB) return catA - catB
    return numOrder(a) - numOrder(b)
  })

  // 判断是否有任何考点
  const hasAnyPoints = pointCodes.some(code => {
    const group = pointsByType[code]
    return group && group.points && group.points.length > 0
  })

  if (!hasAnyPoints) {
    return (
      <section className="handout-page part-page">
        <Title level={3}>三、考点分类</Title>
        <Divider />
        <Text type="secondary">暂无考点分析数据</Text>
      </section>
    )
  }

  // 追踪是否是第一个区块（显示"三、考点分类"标题）
  let isFirstSection = true

  return (
    <>
      {pointCodes.map(code => {
        const group = pointsByType[code]
        if (!group || !group.points || group.points.length === 0) return null

        const section = (
          <PointCodeSection
            key={code}
            code={code}
            name={group.name}
            category={group.category}
            categoryName={group.category_name}
            points={group.points}
            edition={edition}
            showMainTitle={isFirstSection}
          />
        )
        isFirstSection = false
        return section
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
  // C2 (固定搭配) 使用 FixedPhraseSection 风格
  // D1 (词义辨析) 使用 WordAnalysisTable 风格
  // D2 (熟词僻义) 使用 RareMeaningSection 风格
  // 其他使用通用表格

  if (code === 'C2') {
    return <FixedPhraseStyleSection {...{ code, name, category, points, edition, showMainTitle, color, totalPoints }} />
  } else if (code === 'D1') {
    return <WordAnalysisStyleSection {...{ code, name, category, points, edition, showMainTitle, color, totalPoints }} />
  } else if (code === 'D2') {
    return <RareMeaningStyleSection {...{ code, name, category, points, edition, showMainTitle, color, totalPoints }} />
  } else {
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
  // 每页最多显示 4 个考点词（因为每个要展示 4 个选项词）
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

      {/* 4 个选项词表格 - 只展示选项词和释义，不展示排除理由（剧透答案） */}
      {optionWords.length > 1 ? (
        <Table
          dataSource={optionWords.map(word => ({ key: word, word, ...wordAnalysis?.[word] }))}
          size="small"
          pagination={false}
          bordered
          columns={[
            {
              title: '选项词',
              dataIndex: 'word',
              key: 'word',
              width: 80,
              render: (word: string) => <Text>{word}</Text>  // 不高亮正确答案
            },
            {
              title: '释义',
              dataIndex: 'definition',
              key: 'definition',
              render: (def: string) => def || '-'
            }
            // 不展示排除理由、例句、解析 - 这些放在文章后面的答案解析中
          ]}
        />
      ) : (
        // 没有 word_analysis 时的回退展示 - 也不显示正确答案词
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

// 词义辨析卡片
function WordAnalysisCard({ point, edition, index, pointCode, pointName }: { point: PointWordData; edition: string; index: number; pointCode?: string; pointName?: string }) {
  const analysis = point.word_analysis || {}
  const optionWords = Object.keys(analysis)

  return (
    <div style={{ marginBottom: 24 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <Tag color="orange">{index + 1}</Tag>
        {pointCode && pointName && (
          <PointTag point={{ code: pointCode, name: pointName }} size="s" />
        )}
        {/* 不显示正确答案词和出现次数，避免剧透 */}
      </div>

      {/* 三维度表格 - 不展示排除理由和例句（剧透答案） */}
      {optionWords.length > 0 && (
        <Table
          dataSource={optionWords.map(word => ({ key: word, word, ...analysis[word] }))}
          size="small"
          pagination={false}
          bordered
          columns={[
            {
              title: '选项词',
              dataIndex: 'word',
              key: 'word',
              width: 80,
              render: (word: string) => <Text>{word}</Text>  // 不高亮正确答案，避免剧透
            },
            {
              title: '释义',
              dataIndex: 'definition',
              key: 'definition',
            },
            {
              title: '使用对象',
              key: 'user',
              render: (_: unknown, record: { dimensions?: { 使用对象: string } }) => record.dimensions?.使用对象 || '-'
            },
            {
              title: '使用场景',
              key: 'scene',
              render: (_: unknown, record: { dimensions?: { 使用场景: string } }) => record.dimensions?.使用场景 || '-'
            },
            {
              title: '正负态度',
              key: 'attitude',
              render: (_: unknown, record: { dimensions?: { 正负态度: string } }) => record.dimensions?.正负态度 || '-'
            }
            // 不展示排除理由、例句 - 这些放在文章后面的答案解析中
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
  const { code, name, points, edition, showMainTitle, color, totalPoints } = props
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
