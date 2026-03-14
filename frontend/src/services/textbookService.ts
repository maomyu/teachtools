/**
 * 课本单词表服务
 */
import api from './api'

export interface TextbookVocab {
  id: number
  word: string
  pos: string | null
  definition: string
  publisher: string
  grade: string
  semester: string
  unit: string | null
}

export interface TextbookVocabListResponse {
  items: TextbookVocab[]
  total: number
  page: number
  page_size: number
}

export interface TextbookVocabStats {
  total: number
  unique_words: number
  by_publisher: Record<string, number>
  by_grade: Record<string, number>
}

export interface TextbookVocabCreate {
  word: string
  pos?: string | null
  definition: string
  publisher: string
  grade: string
  semester: string
  unit?: string | null
}

export interface TextbookVocabUpdate {
  word?: string
  pos?: string | null
  definition?: string
  publisher?: string
  grade?: string
  semester?: string
  unit?: string | null
}

export interface LookupResponse {
  found: boolean
  entries: TextbookVocab[]
}

// 获取课本单词列表
export async function getTextbookVocabList(params: {
  page?: number
  page_size?: number
  publisher?: string
  grade?: string
  semester?: string
  keyword?: string
}): Promise<TextbookVocabListResponse> {
  const response = await api.get('/textbook-vocab', { params })
  return response.data
}

// 获取统计信息
export async function getTextbookVocabStats(): Promise<TextbookVocabStats> {
  const response = await api.get('/textbook-vocab/stats')
  return response.data
}

// 查询单词是否在课本中
export async function lookupWord(word: string): Promise<LookupResponse> {
  const response = await api.get('/textbook-vocab/lookup', { params: { word } })
  return response.data
}

// 获取单个单词详情
export async function getTextbookVocab(id: number): Promise<TextbookVocab> {
  const response = await api.get(`/textbook-vocab/${id}`)
  return response.data
}

// 创建单词
export async function createTextbookVocab(data: TextbookVocabCreate): Promise<TextbookVocab> {
  const response = await api.post('/textbook-vocab', data)
  return response.data
}

// 更新单词
export async function updateTextbookVocab(id: number, data: TextbookVocabUpdate): Promise<TextbookVocab> {
  const response = await api.put(`/textbook-vocab/${id}`, data)
  return response.data
}

// 删除单词
export async function deleteTextbookVocab(id: number): Promise<void> {
  await api.delete(`/textbook-vocab/${id}`)
}

// 批量删除
export async function batchDeleteTextbookVocab(ids: number[]): Promise<void> {
  await api.post('/textbook-vocab/batch-delete', ids)
}
