/**
 * 讲义转换 API 服务
 *
 * [INPUT]: 依赖 axios
 * [OUTPUT]: 对外提供讲义转换 API
 * [POS]: frontend/src/services 的讲义转换服务
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */
import api from './api'

export interface UploadResponse {
  task_id: string
  filename: string
  file_size: number
}

export interface ProcessProgress {
  progress: number
  message: string
}

export interface ProcessCompleted {
  download_url: string
  answers_removed: number
}

export interface ProcessError {
  error: string
}

/**
 * 上传教师版讲义
 */
export async function uploadHandout(file: File): Promise<UploadResponse> {
  const formData = new FormData()
  formData.append('file', file)

  const response = await api.post<UploadResponse>('/handout/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })

  return response.data
}

/**
 * 获取处理事件的 EventSource URL
 */
export function getProcessEventSourceUrl(
  taskId: string,
  watermarkDensity: 'sparse' | 'medium' | 'dense' = 'sparse',
  watermarkSize: 'small' | 'medium' | 'large' = 'medium'
): string {
  const baseURL = import.meta.env.VITE_API_BASE_URL || ''
  const params = new URLSearchParams({
    task_id: taskId,
    watermark_density: watermarkDensity,
    watermark_size: watermarkSize,
  })
  return `${baseURL}/api/handout/process?${params.toString()}`
}

/**
 * 获取固定图片水印预览 URL
 */
export function getWatermarkPreviewUrl(): string {
  const baseURL = import.meta.env.VITE_API_BASE_URL || ''
  return `${baseURL}/api/handout/watermark-image`
}

/**
 * 获取 PDF 下载 URL
 */
export function getDownloadUrl(taskId: string): string {
  const baseURL = import.meta.env.VITE_API_BASE_URL || ''
  return `${baseURL}/api/handout/download/${taskId}`
}

/**
 * 查询处理状态
 */
export async function getProcessStatus(taskId: string): Promise<{
  task_id: string
  status: string
  progress: number
  message: string
  download_url?: string
  error?: string
}> {
  const response = await api.get(`/handout/status/${taskId}`)
  return response.data
}
