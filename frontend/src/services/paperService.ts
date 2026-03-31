import api from './api'
import type { PaperListResponse, HandoutStatusResponse } from '@/types'

export async function listPapersByGrade(
  grade: string,
  size: number = 500
): Promise<PaperListResponse> {
  const response = await api.get<PaperListResponse>('/papers/', {
    params: { grade, page: 1, size },
  })
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
