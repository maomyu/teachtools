/**
 * 词汇模块API服务
 */
import api from './api'
import type { VocabularyListResponse } from '@/types'

/**
 * 获取词汇列表
 */
export async function getVocabulary(params: {
  grade?: string
  topic?: string
  page?: number
  size?: number
}): Promise<VocabularyListResponse> {
  const response = await api.get<VocabularyListResponse>('/vocabulary', { params })
  return response.data
}

/**
 * 搜索单个词汇
 */
export async function searchVocabulary(word: string): Promise<{
  word: string
  definition?: string
  frequency: number
  occurrences: Array<{
    sentence: string
    passage_id: number
    char_position: number
    end_position?: number
    source?: string
  }>
}> {
  const response = await api.get(`/vocabulary/search`, {
    params: { word },
  })
  return response.data
}
