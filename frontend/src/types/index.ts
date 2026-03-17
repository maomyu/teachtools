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
  explanation?: string
}

/** 排错点 */
export interface RejectionPoint {
  option_word: string
  point_code: string
  explanation?: string
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

/** 新编码到旧类型的映射 */
export const NEW_CODE_TO_LEGACY: Record<string, string> = {
  'C2': '固定搭配',
  'D1': '词义辨析',
  'D2': '熟词僻义',
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
  // 词义辨析
  word_analysis?: Record<string, {
    definition: string
    dimensions?: {
      使用对象: string
      使用场景: string
      正负态度: string
    }
    rejection_reason?: string
  }>
  dictionary_source?: string
  // 熟词僻义
  textbook_meaning?: string
  textbook_source?: string
  context_meaning?: string
  similar_words?: Array<{word: string; textbook: string; rare: string}>
  // 通用
  tips?: string
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

  // 词义辨析专用字段
  word_analysis?: Record<string, {
    definition: string
    dimensions?: {
      使用对象: string
      使用场景: string
      正负态度: string
    }
    rejection_reason?: string
  }>
  dictionary_source?: string

  // 熟词僻义专用字段（作为附加标签）
  is_rare_meaning?: boolean  // 是否包含熟词僻义
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

  // 词义辨析专用
  word_analysis?: Record<string, {
    definition: string
    dimensions?: {
      使用对象: string
      使用场景: string
      正负态度: string
    }
    rejection_reason?: string
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
  exam_type?: string
  semester?: string
  region?: string
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
  edition: 'teacher' | 'student'
  topics: TopicStats[]
  content: TopicContent[]
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

// 词义辨析考点（聚合后）
export interface WordAnalysisPoint {
  word: string
  frequency: number
  definition?: string
  word_analysis?: Record<string, {
    definition: string
    dimensions?: {
      使用对象: string
      使用场景: string
      正负态度: string
    }
    rejection_reason?: string
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

// V2 考点词数据（整合所有类型的字段）
export interface PointWordData {
  word: string
  frequency: number
  definition?: string
  // 词义辨析字段
  word_analysis?: Record<string, {
    definition: string
    dimensions?: {
      使用对象: string
      使用场景: string
      正负态度: string
    }
    rejection_reason?: string
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
