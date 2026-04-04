import api from './api'
import type { PaperListResponse, HandoutStatusResponse } from '@/types'

export type ModuleType = 'reading' | 'cloze' | 'writing'

export async function listPapersByGrade(
  grade: string,
  size: number = 500,
  moduleType?: ModuleType
): Promise<PaperListResponse> {
  const params: Record<string, unknown> = { grade, page: 1, size }
  if (moduleType === 'reading') params.has_reading = true
  else if (moduleType === 'cloze') params.has_cloze = true
  else if (moduleType === 'writing') params.has_writing = true
  const response = await api.get<PaperListResponse>('/papers/', { params })
  return response.data
}

/**
 * 获取试卷讲义生成状态
 */
export async function getHandoutStatus(
  grade: string,
  handoutType: 'reading' | 'cloze' | 'writing'
): Promise<HandoutStatusResponse> {
  const response = await api.get<HandoutStatusResponse>('/papers/handout-status', {
    params: { grade, handout_type: handoutType },
  })
  return response.data
}

/**
 * 批量更新讲义生成状态
 */
export async function batchUpdateHandoutStatus(
  paperIds: number[],
  handoutType: 'reading' | 'cloze' | 'writing'
): Promise<{ message: string; updated_at: string }> {
  const response = await api.post('/papers/batch-update-handout', {
    paper_ids: paperIds,
    handout_type: handoutType,
  })
  return response.data
}

/**
 * 批量重置讲义生成状态（撤回到未生成）
 */
export async function resetHandoutStatus(
  paperIds: number[],
  handoutType: 'reading' | 'cloze' | 'writing'
): Promise<{ message: string }> {
  const response = await api.post('/papers/batch-reset-handout', {
    paper_ids: paperIds,
    handout_type: handoutType,
  })
  return response.data
}
