/**
 * [INPUT]: 依赖 @ant-design/icons 的图标组件
 * [OUTPUT]: 对外提供 StepStatus, PipelineStep, StepUpdateEvent 等类型定义
 * [POS]: frontend/src/types 的核心类型模块，被 ImportPage 和其他页面消费
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */

// ============================================================================
//  步骤化进度类型
// ============================================================================

/** 步骤状态 */
export type StepStatus = 'pending' | 'running' | 'completed' | 'failed' | 'skipped'

/** 单个步骤 */
export interface PipelineStep {
  id: string
  name: string
  description: string
  icon: string
  status: StepStatus
  progress: number
  message: string
  error: string
}

/** SSE步骤更新事件 */
export interface StepUpdateEvent {
  type: 'step_update' | 'completed'
  steps: PipelineStep[]
  current_step: string | null
  overall_progress: number
  result?: ImportResult
}

/** 导入结果（在types中前置声明） */
export interface ImportResult {
  status: 'success' | 'failed' | 'error' | 'exists'
  filename: string
  paper_id?: number
  passages_created?: number
  questions_created?: number
  error?: string
  message?: string
  metadata?: {
    year?: number
    region?: string
    grade?: string
    exam_type?: string
  }
  parse_strategy?: string
  confidence?: number
}

// ============================================================================
//  业务类型
// ============================================================================

// 出处信息
export interface SourceInfo {
  year?: number
  region?: string
  school?: string
  grade?: string
  exam_type?: string
  semester?: string
  filename?: string
}

export interface PaperSummary {
  id: number
  filename: string
  year?: number
  region?: string
  school?: string
  grade?: string
  semester?: string
  exam_type?: string
  version?: string
  import_status?: string
  parse_strategy?: string
  confidence?: number
  error_message?: string
  original_path?: string
  created_at?: string
  updated_at?: string
}

export interface PaperListResponse {
  total: number
  items: PaperSummary[]
}

// 文章
export interface Passage {
  id: number
  paper_id: number
  passage_type: 'C' | 'D'
  title?: string
  content: string
  word_count?: number
  primary_topic?: string
  secondary_topics?: string[]
  topic_confidence?: number
  topic_verified: boolean
  source?: SourceInfo
  created_at: string
}

// 文章列表响应
export interface PassageListResponse {
  total: number
  items: Passage[]
  c_count?: number  // C篇数量
  d_count?: number  // D篇数量
}

// 词汇出现位置
export interface VocabularyOccurrence {
  sentence: string
  passage_id: number
  char_position: number
  end_position?: number
  source?: string  // 出处信息（年份 区县/学校 年级）用于显示
  source_type?: 'reading' | 'cloze'  // 来源类型
  year?: number
  region?: string
  school?: string  // 学校名（如果有）
  grade?: string
  exam_type?: string
  semester?: string
}

// 词汇筛选项响应
export interface VocabularyFiltersResponse {
  grades: string[]
  topics: string[]
  years: number[]
  regions: string[]
  exam_types: string[]
  semesters: string[]
  sources: string[]  // 来源：阅读、完形
}

// 文章详情中的词汇
export interface VocabularyInPassage {
  id: number
  word: string
  definition?: string
  frequency: number
  occurrences: VocabularyOccurrence[]
}

// 题目选项
export interface QuestionOptions {
  A?: string
  B?: string
  C?: string
  D?: string
}

// 题目
export interface Question {
  id: number
  question_number?: number
  question_text: string
  options: QuestionOptions
  correct_answer?: string
  answer_explanation?: string
}

// 文章详情响应
export interface PassageDetail extends Passage {
  vocabulary: VocabularyInPassage[]
  questions: Question[]
  has_questions: boolean
}

// 话题更新请求
export interface TopicUpdateRequest {
  primary_topic: string
  secondary_topics?: string[]
  verified_by?: string
}

// 话题
export interface Topic {
  id: number
  name: string
  grade_level: string
  description?: string
  keywords?: string[]
  sort_order?: number
}

// 话题列表响应
export interface TopicListResponse {
  topics_by_grade: Record<string, Topic[]>
}

// 词汇
export interface Vocabulary {
  id: number
  word: string
  lemma?: string
  definition?: string
  phonetic?: string
  pos?: string
  frequency: number
  sources?: string[]  // 来源：阅读、完形
  occurrences: VocabularyOccurrence[]
}

// 词汇列表响应
export interface VocabularyListResponse {
  total: number
  items: Vocabulary[]
}

// 词汇搜索结果（分页）
export interface VocabularySearchResult {
  word: string
  definition?: string
  frequency: number
  total: number
  page: number
  size: number
  has_more: boolean
  occurrences: VocabularyOccurrence[]
}

// 筛选参数
export interface PassageFilter {
  grade?: string
  topic?: string
  year?: number
  region?: string
  school?: string
  exam_type?: string
  semester?: string
  search?: string
  passage_type?: 'C' | 'D'  // 文章类型筛选
  page?: number
  size?: number
}

// 筛选项响应
export interface PassageFiltersResponse {
  years: number[]
  grades: string[]
  exam_types: string[]
  regions: string[]
  schools: string[]
  topics: string[]
  semesters: string[]
}

// ============================================================================
//  完形填空类型
// ============================================================================

// ============================================================================
//  考点分类系统 V2（新增）
// ============================================================================

/** 考点类型定义 */
export interface PointType {
  code: string              // A1, B2, C2, etc.
  category: string          // A, B, C, D, E
  category_name: string     // 语篇理解类, 逻辑关系类, etc.
  name: string              // 上下文语义推断, 转折对比, etc.
  priority: number          // 1, 2, 3 (P1/P2/P3)
  description?: string
}

/** 辅助考点 */
export interface SecondaryPoint {
  point_code: string
  weight?: 'auxiliary' | 'co-primary'  // V5: auxiliary (辅助) / co-primary (联合主考点)
  explanation?: string
}

/** 排错点 */
export interface RejectionPoint {
  option_word: string
  point_code: string
  rejection_code?: string  // V5: 排错依据编码
  rejection_reason?: string  // V5: 排除原因
  explanation?: string  // V2 兼容
}

/** 考点类型列表响应 */
export interface PointTypeListResponse {
  total: number
  items: PointType[]
}

/** 按大类分组的考点类型响应 */
export interface PointTypeByCategoryResponse {
  A: PointType[]  // 语篇理解类
  B: PointType[]  // 逻辑关系类
  C: PointType[]  // 句法语法类
  D: PointType[]  // 词汇选项类
  E: PointType[]  // 常识主题类
}

/** 大类颜色映射 */
export const CATEGORY_COLORS: Record<string, string> = {
  'A': 'blue',      // 语篇理解
  'B': 'cyan',      // 逻辑关系
  'C': 'green',     // 句法语法
  'D': 'orange',    // 词汇选项
  'E': 'purple',    // 常识主题
}

/** 优先级颜色映射 */
export const PRIORITY_COLORS: Record<number, string> = {
  1: 'red',     // P1 - 核心
  2: 'gold',    // P2 - 重要
  3: 'default', // P3 - 一般
}

/** 大类名称映射 */
export const CATEGORY_NAMES: Record<string, string> = {
  'A': '语篇理解类',
  'B': '逻辑关系类',
  'C': '句法语法类',
  'D': '词汇选项类',
  'E': '常识主题类',
}

/** 优先级名称映射 */
export const PRIORITY_NAMES: Record<number, string> = {
  1: 'P1-核心',
  2: 'P2-重要',
  3: 'P3-一般',
}

/** 旧类型到新编码的映射 */
export const LEGACY_TO_NEW_CODE: Record<string, string> = {
  '固定搭配': 'C2',
  '词义辨析': 'D1',
  '熟词僻义': 'D2',
}

// ============================================================================
//  V2 考点分类系统（5大类16个考点）
// ============================================================================

/** 考点类型完整定义 */
export interface PointTypeDefinition {
  code: string           // A1, B2, etc.
  category: string       // A, B, C, D, E
  categoryName: string   // 语篇理解类, 逻辑关系类, etc.
  name: string           // 上下文语义推断, 转折对比, etc.
  priority: number       // 1, 2, 3 (P1-核心, P2-重要, P3-一般)
  description?: string   // 详细定义
}

/** 所有 16 种考点类型的完整定义（按优先级和编码排序） */
export const ALL_POINT_TYPES: PointTypeDefinition[] = [
  // A. 语篇理解类 (P1-核心)
  { code: 'A1', category: 'A', categoryName: '语篇理解类', name: '上下文语义推断', priority: 1, description: '根据空前空后及前后句推断空格应表达的大致语义' },
  { code: 'A2', category: 'A', categoryName: '语篇理解类', name: '复现与照应', priority: 1, description: '前文或后文出现与答案意思相同、相近、相反或同一主题链上的词' },
  { code: 'A3', category: 'A', categoryName: '语篇理解类', name: '代词指代', priority: 1, description: '通过代词回指确定人物、事物或信息对象' },
  { code: 'A4', category: 'A', categoryName: '语篇理解类', name: '情节/行为顺序', priority: 1, description: '根据故事发展顺序、动作先后顺序判断哪个词最合理' },
  { code: 'A5', category: 'A', categoryName: '语篇理解类', name: '情感态度', priority: 1, description: '根据人物心情、作者评价、语境色彩判断褒贬方向' },
  // B. 逻辑关系类 (P1-核心)
  { code: 'B1', category: 'B', categoryName: '逻辑关系类', name: '并列一致', priority: 1, description: '前后内容语义一致、方向一致、性质相近' },
  { code: 'B2', category: 'B', categoryName: '逻辑关系类', name: '转折对比', priority: 1, description: '前后语义相反或预期相反' },
  { code: 'B3', category: 'B', categoryName: '逻辑关系类', name: '因果关系', priority: 1, description: '前因后果或前果后因' },
  { code: 'B4', category: 'B', categoryName: '逻辑关系类', name: '其他逻辑关系', priority: 1, description: '递进、让步、条件、举例、总结等' },
  // C. 句法语法类 (P2-重要)
  { code: 'C1', category: 'C', categoryName: '句法语法类', name: '词性与句子成分', priority: 2, description: '根据句法位置判断所需词类' },
  { code: 'C2', category: 'C', categoryName: '句法语法类', name: '固定搭配', priority: 2, description: '某些词必须和特定介词、名词、动词或句型一起使用' },
  { code: 'C3', category: 'C', categoryName: '句法语法类', name: '语法形式限制', priority: 2, description: '由时态、语态、主谓一致、非谓语等形式规则限制' },
  // D. 词汇选项类 (P3-一般)
  { code: 'D1', category: 'D', categoryName: '词汇选项类', name: '常规词义辨析', priority: 3, description: '几个选项词性相同、意思相近，需要根据语境精细区分' },
  { code: 'D2', category: 'D', categoryName: '词汇选项类', name: '熟词僻义', priority: 3, description: '常见词在特定语境中使用非常见义项' },
  // E. 常识主题类 (P3-一般)
  { code: 'E1', category: 'E', categoryName: '常识主题类', name: '生活常识/场景常识', priority: 3, description: '根据现实世界常识判断哪个选项合理' },
  { code: 'E2', category: 'E', categoryName: '常识主题类', name: '主题主旨与人物共情', priority: 3, description: '从全文主题和人物心理出发理解作者真正想表达的意思' },
]

/** 按编码快速查找考点类型定义 */
export const POINT_TYPE_BY_CODE: Record<string, PointTypeDefinition> = Object.fromEntries(
  ALL_POINT_TYPES.map(pt => [pt.code, pt])
)

/** 所有考点编码列表（按顺序） */
export const ALL_POINT_CODES = ALL_POINT_TYPES.map(pt => pt.code)

/** 新编码到旧类型的映射 */
export const NEW_CODE_TO_LEGACY: Record<string, string> = {
  'C2': '固定搭配',
  'D1': '词义辨析',
  'D2': '熟词僻义',
  'XX': '待确认分类',
}

// ============================================================================
//  完形考点（V1 兼容）
// ============================================================================

// 完形考点
export interface ClozePoint {
  id: number
  blank_number?: number
  correct_answer?: string
  correct_word?: string
  options?: QuestionOptions
  point_type?: string  // 固定搭配 | 词义辨析 | 熟词僻义
  translation?: string
  explanation?: string
  confusion_words?: Array<{word: string; meaning: string; reason: string}>
  sentence?: string
  // 固定搭配
  phrase?: string
  similar_phrases?: string[]
  // 词义辨析（V5 动态维度）
  word_analysis?: Record<string, {
    definition: string
    collins_frequency?: string  // V5: 柯林斯词频
    dimensions?: Record<string, string>  // V5: 动态维度
  }>
  dictionary_source?: string
  // 熟词僻义
  textbook_meaning?: string
  textbook_source?: string
  context_meaning?: string
  similar_words?: Array<{word: string; textbook: string; rare: string}>
  // 通用
  tips?: string
  // V2 新增
  primary_point_code?: string  // V2 主考点编码 (A1-E2)
  rejection_points?: RejectionPoint[]  // 排错点
}

// 完形词汇
export interface VocabularyInCloze {
  id: number
  word: string
  definition?: string
  frequency: number
  sentence?: string
  char_position?: number
}

// 完形文章
export interface ClozePassage {
  id: number
  paper_id: number
  content: string  // 带空格原文
  original_content?: string  // 完整原文
  word_count?: number
  primary_topic?: string
  secondary_topics?: string[]
  topic_confidence?: number
  source?: SourceInfo
  points: ClozePointNew[]  // 使用 V2 类型，支持 primary_point
}

// 完形列表响应
export interface ClozeListResponse {
  total: number
  items: ClozePassage[]
}

// 完形详情响应 - 继承 V2 格式，兼容旧代码
export interface ClozeDetailResponse extends ClozeDetailNewResponse {}

// ============================================================================
//  完形考点 V2（多标签版本）
// ============================================================================

/** 完形考点 V2 - 支持多标签 */
export interface ClozePointNew {
  id: number
  blank_number?: number
  correct_answer?: string
  correct_word?: string
  options?: QuestionOptions
  sentence?: string

  // === 新考点系统 V2 ===
  primary_point?: PointType           // 主考点
  secondary_points: SecondaryPoint[]  // 辅助考点
  rejection_points: RejectionPoint[]  // 排错点

  // === V5 新增字段 ===
  confidence?: 'high' | 'medium' | 'low'  // 置信度
  confidence_reason?: string              // 置信度依据

  // === 兼容旧系统 ===
  legacy_point_type?: string          // 旧类型: 固定搭配/词义辨析/熟词僻义
  point_type?: string                 // 保留兼容

  // === 解析内容 ===
  translation?: string
  explanation?: string
  confusion_words?: Array<{word: string; meaning: string; reason: string}>
  tips?: string

  // 固定搭配专用字段
  phrase?: string
  similar_phrases?: string[]

  // 词义辨析专用字段（V5 动态维度）
  word_analysis?: Record<string, {
    definition: string
    collins_frequency?: string  // V5: 柯林斯词频★级
    dimensions?: Record<string, string>  // V5: 动态维度（根据词性切换）
  }>
  dictionary_source?: string

  // 熟词僻义专用字段（V5 结构化）
  is_rare_meaning?: boolean
  rare_meaning_info?: {
    common_meaning: string    // 常见义
    context_meaning: string   // 语境义
    textbook_source?: string  // 课本出处
  }
  // 兼容旧字段
  textbook_meaning?: string
  textbook_source?: string
  context_meaning?: string
  similar_words?: Array<{word: string; textbook: string; rare: string}>

  // 状态
  point_verified: boolean
}

/** 完形文章 V2（包含新考点格式） */
export interface ClozePassageNew {
  id: number
  paper_id: number
  content: string
  original_content?: string
  word_count?: number
  primary_topic?: string
  secondary_topics?: string[]
  topic_confidence?: number
  source?: SourceInfo
  points: ClozePointNew[]
}

/** 完形详情响应 V2（新考点分布） */
export interface ClozeDetailNewResponse extends ClozePassageNew {
  // === 新考点分布统计 ===
  point_distribution_by_category: Record<string, number>  // {"A": 5, "B": 3, "C": 2}
  point_distribution_by_priority: Record<string, number>   // {"P1": 8, "P2": 4, "P3": 3}
  // 兼容旧分布
  point_distribution: Record<string, number>  // {"固定搭配": 4, "词义辨析": 5}
  vocabulary: VocabularyInCloze[]
}

/** 完形考点出现位置 V2 */
export interface PointOccurrenceNew {
  sentence: string
  source: string
  blank_number: number
  primary_point?: PointType
  secondary_points: SecondaryPoint[]
  passage_id?: number
  point_id?: number
  analysis?: PointAnalysis
}

/** 完形考点汇总 V2 */
export interface PointSummaryNew {
  word: string
  definition?: string
  frequency: number
  primary_point?: PointType
  occurrences: PointOccurrenceNew[]
  tips?: string
}

/** 完形考点汇总响应 V2 */
export interface PointListNewResponse {
  total: number
  items: PointSummaryNew[]
}

/** 完形筛选参数 V2（新增大类和优先级筛选） */
export interface ClozeFilterNew {
  grade?: string
  topic?: string
  exam_type?: string
  semester?: string
  region?: string
  year?: number
  // === 新增筛选 ===
  point_codes?: string[]   // 按考点编码筛选 [A1, B2, C2]
  categories?: string[]    // 按大类筛选 [A, B, C, D, E]
  priorities?: number[]    // 按优先级筛选 [1, 2, 3]
  // === 兼容旧筛选 ===
  point_type?: string
  page?: number
  size?: number
}

/** 完形筛选项响应 V2 */
export interface ClozeFiltersNewResponse {
  grades: string[]
  topics: string[]
  years: number[]
  regions: string[]
  exam_types: string[]
  semesters: string[]
  // === 新增 ===
  point_codes: string[]   // 所有考点编码
  categories: string[]    // 所有大类
  priorities: number[]    // 所有优先级
  // === 兼容旧 ===
  point_types: string[]
}

// 考点分析详情（嵌套对象）
export interface PointAnalysis {
  // 通用字段
  explanation?: string
  confusion_words?: Array<{word: string; meaning: string; reason: string}>
  tips?: string

  // 固定搭配专用
  phrase?: string
  similar_phrases?: string[]

  // 词义辨析专用（V5 动态维度）
  word_analysis?: Record<string, {
    definition: string
    collins_frequency?: string  // V5: 柯林斯词频★级
    dimensions?: Record<string, string>  // V5: 动态维度
  }>
  dictionary_source?: string

  // 熟词僻义专用
  textbook_meaning?: string
  textbook_source?: string
  context_meaning?: string
  similar_words?: Array<{word: string; textbook: string; rare: string}>
}

// 完形考点出现位置
export interface PointOccurrence {
  sentence: string
  source: string
  blank_number: number
  point_type: string
  passage_id?: number  // 完形文章ID，用于跳转
  point_id?: number    // 考点ID
  // 嵌套分析详情
  analysis?: PointAnalysis
  // 兼容旧数据
  explanation?: string
}

// 完形考点汇总
export interface PointSummary {
  word: string
  definition?: string
  frequency: number
  point_type: string
  occurrences: PointOccurrence[]
  tips?: string  // 聚合后的提示
}

// 完形考点汇总响应
export interface PointListResponse {
  total: number
  items: PointSummary[]
}

// 完形筛选参数
export interface ClozeFilter {
  grade?: string
  topic?: string
  point_type?: string
  category?: string  // 大类筛选 (A/B/C/D/E)
  exam_type?: string
  semester?: string
  region?: string
  school?: string
  year?: number
  page?: number
  size?: number
}

// 完形筛选项响应
export interface ClozeFiltersResponse {
  grades: string[]
  topics: string[]
  years: number[]
  regions: string[]
  schools: string[]
  exam_types: string[]
  point_types: string[]
  semesters: string[]
}

// ============================================================================
//  讲义类型
// ============================================================================

// 讲义主题统计
export interface TopicStats {
  topic: string
  passage_count: number
  recent_years: number[]
}

// 讲义主题列表响应
export interface TopicStatsResponse {
  topics: TopicStats[]
}

// 文章来源（按试卷分组）
export interface ArticleSource {
  year: number
  region: string
  exam_type: string
  semester?: string
  passages: Array<{
    type: string
    id: number
    title?: string
  }>
}

// 讲义词汇（简化版，无 occurrences）
export interface HandoutVocabulary {
  id: number
  word: string
  definition?: string
  phonetic?: string
  frequency: number
  source_type: 'both' | 'reading' | 'cloze'  // 词汇来源
}

// 讲义文章题目
export interface HandoutQuestion {
  number?: number
  text?: string
  options: QuestionOptions
  correct_answer?: string
  explanation?: string
}

// 讲义文章
export interface HandoutPassage {
  id: number
  type: string
  title?: string
  content: string
  word_count?: number
  source?: SourceInfo
  vocabulary: VocabularyInPassage[]
  questions: HandoutQuestion[]
}

// 讲义详情响应
export interface HandoutDetailResponse {
  topic: string
  grade: string
  edition: 'teacher' | 'student'
  part1_article_sources: ArticleSource[]
  part2_vocabulary: HandoutVocabulary[]
  part3_passages: HandoutPassage[]
}

// 主题内容（年级讲义中的单个主题）
export interface TopicContent {
  topic: string
  part1_article_sources: ArticleSource[]
  part2_vocabulary: HandoutVocabulary[]
  part3_passages: HandoutPassage[]
}

// 年级讲义响应（包含所有主题）
export interface GradeHandoutResponse {
  grade: string
  edition: 'teacher' | 'student' | 'both'
  topics: TopicStats[]
  content: TopicContent[] | { teacher: TopicContent[]; student: TopicContent[] }
}

// ============================================================================
//  完形讲义类型
// ============================================================================

// 完形主题统计
export interface ClozeTopicStats {
  topic: string
  passage_count: number
  recent_years: number[]
}

// 词义辨析考点（聚合后，V5 动态维度）
export interface WordAnalysisPoint {
  word: string
  frequency: number
  definition?: string
  word_analysis?: Record<string, {
    definition: string
    collins_frequency?: string  // V5: 柯林斯词频
    dimensions?: Record<string, string>  // V5: 动态维度
  }>
  dictionary_source?: string
  occurrences: PointOccurrence[]
}

// 固定搭配考点（聚合后）
export interface FixedPhrasePoint {
  word: string
  frequency: number
  phrase?: string
  similar_phrases?: string[]
  occurrences: PointOccurrence[]
}

// 熟词僻义考点（聚合后）
export interface RareMeaningPoint {
  word: string
  frequency: number
  textbook_meaning?: string
  textbook_source?: string
  context_meaning?: string
  similar_words?: Array<{ word: string; textbook: string; rare: string }>
  occurrences: PointOccurrence[]
}

// V2 考点词数据（整合所有类型的字段，V5 动态维度）
export interface PointWordData {
  word: string
  frequency: number
  definition?: string
  // 词义辨析字段
  word_analysis?: Record<string, {
    definition: string
    collins_frequency?: string  // V5: 柯林斯词频
    dimensions?: Record<string, string>  // V5: 动态维度
  }>
  dictionary_source?: string
  // 固定搭配字段
  phrase?: string
  similar_phrases?: string[]
  // 熟词僻义字段
  textbook_meaning?: string
  textbook_source?: string
  context_meaning?: string
  similar_words?: Array<{ word: string; textbook: string; rare: string }>
  // 出现记录
  occurrences: PointOccurrence[]
}

// V2 考点分组数据（按编码分组）
export interface PointGroupData {
  code: string              // A1, B2, C2, etc.
  name: string              // 上下文语义推断, 转折对比, etc.
  category: string          // A, B, C, D, E
  category_name: string     // 语篇理解类, 逻辑关系类, etc.
  points: PointWordData[]   // 该考点的所有考点词
}

// 按考点编码分组的考点（V2）
export interface PointsByType {
  [pointCode: string]: PointGroupData  // A1, A2, ..., E2
}

// 完形讲义文章
export interface ClozeHandoutPassage {
  id: number
  content: string
  word_count?: number
  source?: SourceInfo
  points: ClozePoint[]
}

// 完形主题内容
export interface ClozeTopicContent {
  topic: string
  part1_article_sources: ArticleSource[]
  part2_vocabulary: HandoutVocabulary[]
  part3_points_by_type: PointsByType
  part4_passages: ClozeHandoutPassage[]
}

// 完形讲义详情响应
export interface ClozeHandoutDetailResponse {
  topic: string
  grade: string
  edition: 'teacher' | 'student'
  part1_article_sources: ArticleSource[]
  part2_vocabulary: HandoutVocabulary[]
  part3_points_by_type: PointsByType
  part4_passages: ClozeHandoutPassage[]
}

// 完形年级讲义响应
export interface ClozeGradeHandoutResponse {
  grade: string
  edition: 'teacher' | 'student'
  topics: ClozeTopicStats[]
  content: ClozeTopicContent[]
}

// ============================================================================
//  批量删除类型
// ============================================================================

/** 批量删除响应 */
export interface BatchDeleteResponse {
  message: string
  deleted_count: number
  paper_deleted: number  // 被删除的试卷数量
}

// ============================================================================
//  作文模块类型
// ============================================================================

/** 作文任务 */
export interface WritingCategoryNode {
  id: number
  code: string
  name: string
  level: number
  parent_id?: number
  path: string
  template_key: string
}

export interface WritingTask {
  id: number
  paper_id: number
  task_content: string
  requirements?: string
  word_limit?: string
  points_value?: string
  grade?: string
  semester?: string
  exam_type?: string
  group_category?: WritingCategoryNode
  major_category?: WritingCategoryNode
  category?: WritingCategoryNode
  category_confidence: number
  category_reasoning?: string
  training_word_target: string
  source?: SourceInfo
  created_at: string
}

/** 作文列表响应 */
export interface WritingTaskListResponse {
  total: number
  items: WritingTask[]
  grade_counts?: Record<string, number>
}

/** 作文模板 */
export interface WritingTemplate {
  id: number
  category: WritingCategoryNode
  template_name: string
  template_content: string
  tips?: string
  structure?: string
  // === 新增专业要素字段 ===
  opening_sentences?: string    // 开头句型（JSON数组）
  closing_sentences?: string    // 结尾句型（JSON数组）
  transition_words?: string     // 过渡词汇（JSON数组）
  advanced_vocabulary?: string  // 高级词汇替换（JSON数组）
  grammar_points?: string       // 语法要点（JSON数组）
  scoring_criteria?: string     // 评分标准提示（JSON）
  created_at: string
}

/** 作文范文 */
export interface WritingSample {
  id: number
  task_id?: number
  template_id?: number
  sample_content: string
  sample_type: 'AI生成' | '人工编写' | '真题范文'
  score_level?: string  // 一档/二档/三档
  // === 新增评估字段 ===
  word_count?: number         // 实际字数
  highlights?: string         // 亮点表达（JSON数组）
  grammar_analysis?: string   // 语法分析（JSON）
  issues?: string             // 存在问题（JSON数组，用于三档文）
  translation?: string        // 中文翻译
  created_at: string
}

/** 作文详情响应 */
export interface WritingTaskDetail extends WritingTask {
  templates: WritingTemplate[]
  samples: WritingSample[]
}

/** 作文筛选参数 */
export interface WritingFilter {
  page?: number
  size?: number
  grade?: string
  semester?: string
  exam_type?: string
  group_category_id?: number
  major_category_id?: number
  category_id?: number
  search?: string
}

/** 作文筛选项响应 */
export interface WritingFiltersResponse {
  grades: string[]
  semesters: string[]
  exam_types: string[]
  groups: WritingCategoryNode[]
  major_categories: WritingCategoryNode[]
  categories: WritingCategoryNode[]
}

/** 文体识别响应 */
export interface WritingTypeDetectResponse {
  task_id: number
  group_category?: WritingCategoryNode
  major_category?: WritingCategoryNode
  category?: WritingCategoryNode
  confidence: number
  reasoning?: string
}

/** 批量生成响应 */
export interface BatchGenerateResponse {
  success_count: number
  fail_count: number
  results: Array<{
    task_id: number
    success: boolean
    sample_id?: number
    error?: string
  }>
}

// ============================================================================
//  作文讲义类型
// ============================================================================

/** 作文讲义子类统计 */
export interface WritingHandoutCategorySummary {
  group_name: string
  major_category_name: string
  category_name: string
  task_count: number
  sample_count: number
  recent_years: number[]
  applicable_ranges: string[]
}

/** 写作框架段落 */
export interface WritingFrameworkSection {
  name: string  // 开头句/背景句/中心句/主体段/结尾句
  description: string
  examples: string[]
}

/** 写作框架 */
export interface WritingFramework {
  title: string
  category_name: string
  sections: WritingFrameworkSection[]
}

/** 高频表达 */
export interface HighFrequencyExpression {
  category: string  // 开头句型/结尾句型/过渡词汇/高级词汇
  items: string[]
}

/** 重点句标注 */
export interface HighlightedSentence {
  sentence: string
  highlight_type: string  // 高级词汇/复杂句型/地道表达/过渡词
  explanation: string
}

/** 讲义范文来源 */
export interface HandoutSampleSource {
  year?: number
  region?: string
  exam_type?: string
  semester?: string
}

/** 讲义范文 */
export interface HandoutSample {
  id: number
  task_content: string
  sample_content: string
  translation?: string  // 中文翻译
  word_count?: number
  highlighted_sentences: HighlightedSentence[]
  source?: HandoutSampleSource
}

/** 作文讲义单个子类区块 */
export interface WritingHandoutCategorySection {
  group_category: WritingCategoryNode
  major_category: WritingCategoryNode
  category: WritingCategoryNode
  summary: WritingHandoutCategorySummary
  frameworks: WritingFramework[]
  expressions: HighFrequencyExpression[]
  samples: HandoutSample[]
}

/** 作文讲义一级分组 */
export interface WritingHandoutGroup {
  group_category: WritingCategoryNode
  sections: WritingHandoutCategorySection[]
}

/** 年级作文讲义响应 */
export interface WritingGradeHandoutResponse {
  grade: string
  edition: string
  total_task_count: number
  groups: WritingHandoutGroup[]
}

// ============================================================================
//  讲义生成状态类型
// ============================================================================

/** 试卷讲义状态 */
export interface PaperHandoutStatus {
  id: number
  filename: string
  year?: number
  region?: string
  exam_type?: string
  generated_at?: string
}

/** 讲义状态响应 */
export interface HandoutStatusResponse {
  generated: PaperHandoutStatus[]
  not_generated: PaperHandoutStatus[]
}
