/**
 * 作文模块 API 服务
 *
 * [INPUT]: 依赖 api 服务、类型定义
 * [OUTPUT]: 对外提供作文相关的 API 调用函数
 * [POS]: frontend/src/services 的作文服务
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */
import api from './api'
import type {
  WritingTaskListResponse,
  WritingTaskDetail,
  WritingFilter,
  WritingFiltersResponse,
  WritingTypeDetectResponse,
  BatchGenerateResponse,
  WritingTemplate,
  WritingSample,
  WritingGradeHandoutResponse,
  WritingHandoutDetailResponse,
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


// ==============================================================================
//                              筛选项
// ==============================================================================

/**
 * 获取作文筛选项
 */
export async function getWritingFilters(): Promise<WritingFiltersResponse> {
  const response = await api.get<WritingFiltersResponse>('/writings/filters')
  return response.data
}


// ==============================================================================
//                              列表查询
// ==============================================================================

/**
 * 获取作文列表
 */
export async function getWritings(params: WritingFilter): Promise<WritingTaskListResponse> {
  const response = await api.get<WritingTaskListResponse>('/writings', { params })
  return response.data
}

/**
 * 获取作文详情
 */
export async function getWritingDetail(id: number): Promise<WritingTaskDetail> {
  const response = await api.get<WritingTaskDetail>(`/writings/${id}`)
  return response.data
}


// ==============================================================================
//                              文体识别
// ==============================================================================

/**
 * 智能文体识别
 */
export async function detectWritingType(id: number): Promise<WritingTypeDetectResponse> {
  const response = await api.post<WritingTypeDetectResponse>(`/writings/${id}/detect-type`)
  return response.data
}


// ==============================================================================
//                              范文生成
// ==============================================================================

export interface SampleGenerateRequest {
  template_id?: number
  score_level?: string  // 一档/二档/三档
}

/**
 * 生成单篇范文
 */
export async function generateSample(
  taskId: number,
  request: SampleGenerateRequest = {}
): Promise<WritingSample> {
  const response = await api.post<WritingSample>(
    `/writings/${taskId}/generate-sample`,
    request
  )
  return response.data
}

export interface BatchGenerateRequest {
  task_ids: number[]
  score_level?: string
}

/**
 * 批量生成范文
 */
export async function batchGenerateSamples(
  request: BatchGenerateRequest
): Promise<BatchGenerateResponse> {
  const response = await api.post<BatchGenerateResponse>('/writings/batch-generate', request)
  return response.data
}


// ==============================================================================
//                              删除
// ==============================================================================

/**
 * 删除作文
 */
export async function deleteWriting(id: number): Promise<{ message: string }> {
  const response = await api.delete(`/writings/${id}`)
  return response.data
}

export interface BatchDeleteRequest {
  task_ids: number[]
}

/**
 * 批量删除作文
 */
export async function batchDeleteWritings(
  request: BatchDeleteRequest
): Promise<{ message: string }> {
  const response = await api.post('/writings/batch-delete', request)
  return response.data
}


// ==============================================================================
//                              范文删除
// ==============================================================================

/**
 * 删除单个范文
 */
export async function deleteSample(
  taskId: number,
  sampleId: number
): Promise<{ message: string }> {
  const response = await api.delete(`/writings/${taskId}/samples/${sampleId}`)
  return response.data
}


// ==============================================================================
//                              模板
// ==============================================================================

/**
 * 获取模板
 */
export async function getTemplate(
  writingType: string,
  applicationType?: string
): Promise<WritingTemplate> {
  const response = await api.get<WritingTemplate>('/writings/template', {
    params: {
      writing_type: writingType,
      application_type: applicationType,
    },
  })
  return response.data
}


// ==============================================================================
//                              讲义功能
// ==============================================================================

/**
 * 获取年级作文讲义（含所有话题）
 */
export async function getWritingHandout(
  grade: string,
  edition: 'teacher' | 'student' = 'teacher',
  paperIds?: number[]
): Promise<WritingGradeHandoutResponse> {
  const response = await api.get<WritingGradeHandoutResponse>(
    `/writings/handouts/${grade}`,
    { params: buildHandoutParams(edition, paperIds) }
  )
  return response.data
}

/**
 * 获取年级话题统计
 */
export async function getWritingHandoutTopics(
  grade: string
): Promise<{ grade: string; topics: Array<{ topic: string; task_count: number; sample_count: number; recent_years: number[] }> }> {
  const response = await api.get(`/writings/handouts/${grade}/topics`)
  return response.data
}

/**
 * 获取单话题作文讲义详情
 */
export async function getWritingHandoutDetail(
  grade: string,
  topic: string,
  edition: 'teacher' | 'student' = 'teacher',
  paperIds?: number[]
): Promise<WritingHandoutDetailResponse> {
  const encodedTopic = encodeURIComponent(topic)
  const response = await api.get<WritingHandoutDetailResponse>(
    `/writings/handouts/${grade}/topics/${encodedTopic}`,
    { params: buildHandoutParams(edition, paperIds) }
  )
  return response.data
}
