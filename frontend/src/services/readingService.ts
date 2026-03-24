/**
 * 阅读模块API服务
 *
 * [INPUT]: 依赖 api 服务、类型定义
 * [OUTPUT]: 对外提供阅读相关的 API 调用函数
 * [POS]: frontend/src/services 的阅读服务
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */
import api from './api'
import type {
  PassageListResponse,
  PassageDetail,
  TopicUpdateRequest,
  TopicListResponse,
  PassageFilter,
  PassageFiltersResponse,
  // 讲义相关类型
  TopicStatsResponse,
  HandoutDetailResponse,
  GradeHandoutResponse,
  // 批量删除
  BatchDeleteResponse,
} from '@/types'

function buildHandoutParams(
  edition?: 'teacher' | 'student',
  paperIds?: number[]
): URLSearchParams | undefined {
  const params = new URLSearchParams()
  if (edition) {
    params.append('edition', edition)
  }
  ;(paperIds || []).forEach((paperId) => params.append('paper_ids', String(paperId)))
  return Array.from(params.keys()).length > 0 ? params : undefined
}

/**
 * 获取文章筛选项（动态从数据库获取）
 */
export async function getPassageFilters(): Promise<PassageFiltersResponse> {
  const response = await api.get<PassageFiltersResponse>('/passages/filters')
  return response.data
}

/**
 * 获取文章列表
 */
export async function getPassages(params: PassageFilter): Promise<PassageListResponse> {
  const response = await api.get<PassageListResponse>('/passages', { params })
  return response.data
}

/**
 * 获取文章详情
 */
export async function getPassage(id: number): Promise<PassageDetail> {
  const response = await api.get<PassageDetail>(`/passages/${id}`)
  return response.data
}

/**
 * 更新文章话题
 */
export async function updatePassageTopic(
  id: number,
  data: TopicUpdateRequest
): Promise<{ message: string; passage_id: number }> {
  const response = await api.put(`/passages/${id}/topic`, data)
  return response.data
}

/**
 * 获取话题列表
 */
export async function getTopics(grade?: string): Promise<TopicListResponse> {
  const response = await api.get<TopicListResponse>('/topics', {
    params: grade ? { grade } : undefined,
  })
  return response.data
}

/**
 * 删除文章
 */
export async function deletePassage(id: number): Promise<{ message: string; passage_id: number }> {
  const response = await api.delete(`/passages/${id}`)
  return response.data
}

/**
 * 批量删除文章
 */
export async function batchDeletePassages(ids: number[]): Promise<BatchDeleteResponse> {
  const response = await api.post<BatchDeleteResponse>('/passages/batch-delete', ids)
  return response.data
}

// ============================================================================
//  讲义相关 API
// ============================================================================

/**
 * 获取某年级的主题统计（按考频降序）
 */
export async function getTopicStatsForGrade(grade: string): Promise<TopicStatsResponse> {
  const response = await api.get<TopicStatsResponse>(`/passages/handouts/${grade}/topics`)
  return response.data
}

/**
 * 获取讲义详情（三段式结构）
 */
export async function getHandoutDetail(
  grade: string,
  topic: string,
  edition: 'teacher' | 'student' = 'teacher',
  paperIds?: number[]
): Promise<HandoutDetailResponse> {
  const response = await api.get<HandoutDetailResponse>(
    `/passages/handouts/${grade}/topics/${topic}`,
    { params: buildHandoutParams(edition, paperIds) }
  )
  return response.data
}

/**
 * 获取年级完整讲义（包含所有主题）
 */
export async function getGradeHandout(
  grade: string,
  edition: 'teacher' | 'student' = 'teacher',
  paperIds?: number[]
): Promise<GradeHandoutResponse> {
  const response = await api.get<GradeHandoutResponse>(
    `/passages/handouts/${grade}`,
    { params: buildHandoutParams(edition, paperIds) }
  )
  return response.data
}
