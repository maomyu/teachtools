/**
 * 阅读模块API服务
 */
import api from './api'
import type {
  PassageListResponse,
  PassageDetail,
  TopicUpdateRequest,
  TopicListResponse,
  PassageFilter,
} from '@/types'

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
