/**
 * 类型定义
 */

// 出处信息
export interface SourceInfo {
  year?: number
  region?: string
  school?: string
  grade?: string
  exam_type?: string
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
  char_position: number
  end_position?: number
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

// 筛选参数
export interface PassageFilter {
  grade?: string
  topic?: string
  year?: number
  region?: string
  search?: string
  page?: number
  size?: number
}
