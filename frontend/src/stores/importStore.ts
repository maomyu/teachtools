import { create } from 'zustand'
import type { UploadFile } from 'antd/es/upload/interface'

import type {
  PipelineStep,
  StepUpdateEvent,
  ImportResult,
} from '@/types'

interface ImportSummary {
  successCount: number
  failedCount: number
  existsCount: number
}

interface ImportStoreState {
  fileList: UploadFile[]
  uploading: boolean
  results: ImportResult[]
  steps: PipelineStep[]
  currentStep: string | null
  overallProgress: number
  currentFileIndex: number
  activeFileName: string | null
  lastSummary: ImportSummary | null
  setFileList: (files: UploadFile[]) => void
  addFiles: (files: UploadFile[]) => void
  removeFile: (file: UploadFile) => void
  clear: () => void
  startImport: () => Promise<ImportSummary>
}

const initialState = {
  fileList: [] as UploadFile[],
  uploading: false,
  results: [] as ImportResult[],
  steps: [] as PipelineStep[],
  currentStep: null as string | null,
  overallProgress: 0,
  currentFileIndex: 0,
  activeFileName: null as string | null,
  lastSummary: null as ImportSummary | null,
}

function parseSSEEvent(line: string): StepUpdateEvent | null {
  if (!line.startsWith('data: ')) return null

  try {
    return JSON.parse(line.slice(6)) as StepUpdateEvent
  } catch {
    return null
  }
}

async function uploadWithProgress(
  file: UploadFile,
  onProgress: (event: StepUpdateEvent) => void
): Promise<ImportResult> {
  const formData = new FormData()
  const rawFile = file.originFileObj || file
  formData.append('file', rawFile as Blob)

  const params = new URLSearchParams()
  params.append('force', 'true')

  const response = await fetch(`/api/papers/upload-with-progress?${params.toString()}`, {
    method: 'POST',
    body: formData,
  })

  if (!response.ok) {
    throw new Error(`导入请求失败: ${response.status}`)
  }

  const reader = response.body?.getReader()
  if (!reader) {
    throw new Error('无法读取响应流')
  }

  const decoder = new TextDecoder()
  let buffer = ''
  let lastResult: ImportResult | null = null

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''

    for (const line of lines) {
      const event = parseSSEEvent(line)
      if (!event) continue

      onProgress(event)

      if (event.type === 'completed' && event.result) {
        lastResult = event.result
      }
    }
  }

  if (buffer) {
    const event = parseSSEEvent(buffer)
    if (event) {
      onProgress(event)
      if (event.type === 'completed' && event.result) {
        lastResult = event.result
      }
    }
  }

  return lastResult ?? {
    status: 'error',
    filename: file.name,
    error: '未收到完成信号',
  }
}

export const useImportStore = create<ImportStoreState>((set, get) => ({
  ...initialState,

  setFileList: (files) => {
    if (get().uploading) return
    set({ fileList: files })
  },

  addFiles: (files) => {
    if (get().uploading || files.length === 0) return
    set((state) => ({ fileList: [...state.fileList, ...files] }))
  },

  removeFile: (file) => {
    if (get().uploading) return
    set((state) => ({
      fileList: state.fileList.filter((item) => item.uid !== file.uid),
    }))
  },

  clear: () => {
    if (get().uploading) return
    set({ ...initialState })
  },

  startImport: async () => {
    const { fileList, uploading } = get()
    if (uploading || fileList.length === 0) {
      return get().lastSummary ?? { successCount: 0, failedCount: 0, existsCount: 0 }
    }

    const filesToImport = [...fileList]
    const uploadResults: ImportResult[] = []

    set({
      uploading: true,
      results: [],
      steps: [],
      currentStep: null,
      overallProgress: 0,
      currentFileIndex: 0,
      activeFileName: null,
      lastSummary: null,
    })

    for (let i = 0; i < filesToImport.length; i += 1) {
      const file = filesToImport[i]
      set({
        currentFileIndex: i + 1,
        activeFileName: file.name,
      })

      try {
        const result = await uploadWithProgress(file, (event) => {
          set({
            steps: event.steps,
            currentStep: event.current_step,
            overallProgress: event.overall_progress,
          })
        })

        uploadResults.push(result)
      } catch (error) {
        uploadResults.push({
          status: 'error',
          filename: file.name,
          error: error instanceof Error ? error.message : '上传失败',
        })
      }

      set({ results: [...uploadResults] })
    }

    const summary = {
      successCount: uploadResults.filter((item) => item.status === 'success').length,
      failedCount: uploadResults.filter((item) => item.status === 'failed' || item.status === 'error').length,
      existsCount: uploadResults.filter((item) => item.status === 'exists').length,
    }

    set({
      uploading: false,
      currentStep: null,
      activeFileName: null,
      overallProgress: uploadResults.length > 0 ? 100 : 0,
      lastSummary: summary,
    })

    return summary
  },
}))
