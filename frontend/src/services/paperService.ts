import api from './api'
import type { PaperListResponse } from '@/types'

export async function listPapersByGrade(
  grade: string,
  size: number = 500
): Promise<PaperListResponse> {
  const response = await api.get<PaperListResponse>('/papers/', {
    params: { grade, page: 1, size },
  })
  return response.data
}
