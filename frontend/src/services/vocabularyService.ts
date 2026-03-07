/**
 * 词汇模块API服务
 *
 * [INPUT]: 依赖 @/services/api 的 axios 实例
 * [OUTPUT]: 对外提供词汇列表、筛选项、搜索接口
 * [POS]: frontend/src/services 的词汇API服务
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */
import api from './api'
import type { VocabularyListResponse, VocabularyFiltersResponse } from '@/types'

/**
 * 获取词汇筛选项
 */
export async function getVocabularyFilters(): Promise<VocabularyFiltersResponse> {
  const response = await api.get<VocabularyFiltersResponse>('/vocabulary/filters')
  return response.data
}

/**
 * 获取词汇列表（支持多维筛选）
 */
export async function getVocabulary(params: {
  grade?: string
  topic?: string
  year?: number
  region?: string
  exam_type?: string
  semester?: string
  min_frequency?: number
  search?: string
  page?: number
  size?: number
}): Promise<VocabularyListResponse> {
  const response = await api.get<VocabularyListResponse>('/vocabulary', { params })
  return response.data
}

/**
 * 搜索单个词汇
 */
export interface VocabularySearchParams {
  word: string
  page?: number
  size?: number
  // 筛选条件（与词汇列表一致）
  grade?: string
  topic?: string
  year?: number
  region?: string
  exam_type?: string
  semester?: string
}

export interface VocabularySearchResult {
  word: string
  definition?: string
  frequency: number
  total: number
  page: number
  size: number
  has_more: boolean
  occurrences: Array<{
    sentence: string
    passage_id: number
    char_position: number
    end_position?: number
    source?: string
  }>
}

export async function searchVocabulary(
  word: string,
  page: number = 1,
  size: number = 10,
  filters?: {
    grade?: string
    topic?: string
    year?: number
    region?: string
    exam_type?: string
    semester?: string
  }
): Promise<VocabularySearchResult> {
  const response = await api.get(`/vocabulary/search`, {
    params: {
      word,
      page,
      size,
      ...filters,  // 展开筛选条件
    },
  })
  return response.data
}
