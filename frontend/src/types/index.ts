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
}

// 词汇出现位置
export interface VocabularyOccurrence {
  sentence: string
  passage_id: number
  char_position: number
  end_position?: number
  source?: string  // 出处信息（年份 区县 年级）用于显示
  year?: number
  region?: string
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
