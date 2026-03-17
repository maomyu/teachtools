/**
 * [INPUT]: 依赖 src/services/api.ts 的 axios 实例
 * [OUTPUT]: 对外提供完形填空相关的 API 调用方法
 * [POS]: frontend/src/services 的完形 API 服务
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */
import api from './api'
import type {
  ClozeListResponse,
  ClozeDetailNewResponse,
  PointListResponse,
  ClozeFiltersResponse,
  ClozeFilter,
  PointTypeListResponse,
  PointTypeByCategoryResponse,
  // 批量删除
  BatchDeleteResponse,
} from '../types'

/**
 * 获取完形文章列表
 */
export async function getClozeList(params: ClozeFilter): Promise<ClozeListResponse> {
  const response = await api.get<ClozeListResponse>('/cloze', { params })
  return response.data
}

/**
 * 获取完形文章详情
 */
export async function getCloze(id: number): Promise<ClozeDetailNewResponse> {
  const response = await api.get<ClozeDetailNewResponse>(`/cloze/${id}`)
  return response.data
}

/**
 * 获取考点汇总
 */
export async function getPointList(params: {
  point_type?: string
  grade?: string
  keyword?: string
  page?: number
  size?: number
}): Promise<PointListResponse> {
  const response = await api.get<PointListResponse>('/cloze/points/summary', { params })
  return response.data
}

/**
 * 更新完形话题
 */
export async function updateClozeTopic(
  id: number,
  data: { primary_topic: string; secondary_topics?: string[]; verified?: boolean }
): Promise<void> {
  await api.put(`/cloze/${id}/topic`, data)
}

/**
 * 更新考点分析
 */
export async function updatePointAnalysis(
  blankId: number,
  data: {
    point_type: string
    explanation?: string
    translation?: string
    confusion_words?: Array<{word: string; meaning: string; reason: string}>
    verified?: boolean
  }
): Promise<void> {
  await api.put(`/cloze/blanks/${blankId}/point`, data)
}

/**
 * 删除完形文章
 */
export async function deleteCloze(id: number): Promise<{ message: string; cloze_id: number }> {
  const response = await api.delete(`/cloze/${id}`)
  return response.data
}

/**
 * 批量删除完形文章
 */
export async function batchDeleteClozes(ids: number[]): Promise<BatchDeleteResponse> {
  const response = await api.post<BatchDeleteResponse>('/cloze/batch-delete', ids)
  return response.data
}

/**
 * 获取完形筛选器选项
 */
export async function getClozeFilters(): Promise<ClozeFiltersResponse> {
  const response = await api.get<ClozeFiltersResponse>('/cloze/filters')
  return response.data
}

// ============================================================================
//  讲义 API
// ============================================================================

import type {
  ClozeTopicStats,
  ClozeHandoutDetailResponse,
  ClozeGradeHandoutResponse,
} from '@/types'

/**
 * 获取某年级的完形主题统计
 */
export async function getClozeTopicStats(grade: string): Promise<{ topics: ClozeTopicStats[] }> {
  const response = await api.get(`/cloze/handouts/${grade}/topics`)
  return response.data
}

/**
 * 获取某年级某主题的完形讲义详情
 */
export async function getClozeHandoutDetail(
  grade: string,
  topic: string,
  edition: 'teacher' | 'student' = 'teacher'
): Promise<ClozeHandoutDetailResponse> {
  const response = await api.get(
    `/cloze/handouts/${grade}/topics/${encodeURIComponent(topic)}`,
    { params: { edition } }
  )
  return response.data
}

/**
 * 获取某年级的完整完形讲义
 */
export async function getClozeGradeHandout(
  grade: string,
  edition: 'teacher' | 'student' = 'teacher'
): Promise<ClozeGradeHandoutResponse> {
  const response = await api.get(
    `/cloze/handouts/${grade}`,
    { params: { edition } }
  )
  return response.data
}

// ============================================================================
//  考点类型定义 API（V2 新增）
// ============================================================================

/**
 * 获取所有考点类型定义
 */
export async function getPointTypes(): Promise<PointTypeListResponse> {
  const response = await api.get<PointTypeListResponse>('/cloze/point-types')
  return response.data
}

/**
 * 按大类获取考点类型定义
 */
export async function getPointTypesByCategory(): Promise<PointTypeByCategoryResponse> {
  const response = await api.get<PointTypeByCategoryResponse>('/cloze/point-types/by-category')
  return response.data
}
