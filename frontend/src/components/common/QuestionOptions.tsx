import type { CSSProperties } from 'react'
import { Typography } from 'antd'

import type { QuestionOptions as QuestionOptionsType } from '@/types'

const { Text } = Typography

const IMAGE_TOKEN_REGEX = /\[IMAGE:(.+?)\]/g
const PENDING_IMAGE_TOKEN_REGEX = /\[IMAGE\]/g
const OPTION_KEYS = ['A', 'B', 'C', 'D'] as const

export interface ParsedOptionContent {
  text: string
  imageUrls: string[]
  pendingImageCount: number
}

export function parseOptionContent(value?: string): ParsedOptionContent {
  if (!value) {
    return { text: '', imageUrls: [], pendingImageCount: 0 }
  }

  const imageUrls: string[] = []
  const pendingImageCount = (value.match(PENDING_IMAGE_TOKEN_REGEX) || []).length
  const text = value
    .replace(IMAGE_TOKEN_REGEX, (_matched, url: string) => {
      imageUrls.push(url.trim())
      return ' '
    })
    .replace(PENDING_IMAGE_TOKEN_REGEX, ' ')
    .replace(/\s+/g, ' ')
    .trim()

  return {
    text,
    imageUrls,
    pendingImageCount,
  }
}

export function hasRenderableOption(value?: string): boolean {
  const parsed = parseOptionContent(value)
  return Boolean(parsed.text || parsed.imageUrls.length || parsed.pendingImageCount)
}

interface QuestionOptionsProps {
  options?: QuestionOptionsType | null
  fontSize?: number
  imageMaxWidth?: number
  imageMaxHeight?: number
  style?: CSSProperties
  optionSpacing?: number
}

export function QuestionOptions({
  options,
  fontSize = 12,
  imageMaxWidth = 220,
  imageMaxHeight = 120,
  style,
  optionSpacing = 8,
}: QuestionOptionsProps) {
  if (!options) {
    return null
  }

  const renderableOptions = OPTION_KEYS.filter((key) =>
    hasRenderableOption(options[key as keyof QuestionOptionsType])
  )

  if (renderableOptions.length === 0) {
    return null
  }

  return (
    <div style={style}>
      {renderableOptions.map((key) => {
        const optionValue = options[key as keyof QuestionOptionsType]
        const parsed = parseOptionContent(optionValue)

        return (
          <div
            key={key}
            style={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: 8,
              marginBottom: optionSpacing,
            }}
          >
            <Text strong style={{ fontSize }}>
              {key}.
            </Text>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, flex: 1 }}>
              {parsed.text && (
                <Text style={{ fontSize, whiteSpace: 'pre-wrap' }}>
                  {parsed.text}
                </Text>
              )}

              {parsed.imageUrls.map((imageUrl, index) => (
                <img
                  key={`${key}-${index}-${imageUrl}`}
                  src={imageUrl}
                  alt={`选项 ${key}`}
                  style={{
                    maxWidth: imageMaxWidth,
                    maxHeight: imageMaxHeight,
                    width: 'auto',
                    height: 'auto',
                    border: '1px solid #d9d9d9',
                    borderRadius: 4,
                    padding: 2,
                    objectFit: 'contain',
                    background: '#fff',
                  }}
                />
              ))}

              {parsed.pendingImageCount > 0 && (
                <Text type="secondary" style={{ fontSize }}>
                  图片待提取
                </Text>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
