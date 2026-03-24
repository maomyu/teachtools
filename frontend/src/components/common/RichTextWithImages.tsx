import type { CSSProperties } from 'react'
import { Typography } from 'antd'

import { parseOptionContent } from '@/components/common/QuestionOptions'

const { Text } = Typography

interface RichTextWithImagesProps {
  value?: string | null
  fontSize?: number
  imageMaxWidth?: number
  imageMaxHeight?: number
  strong?: boolean
  textStyle?: CSSProperties
  style?: CSSProperties
  imageAlt?: string
}

export function RichTextWithImages({
  value,
  fontSize = 14,
  imageMaxWidth = 280,
  imageMaxHeight = 180,
  strong = false,
  textStyle,
  style,
  imageAlt = '题目配图',
}: RichTextWithImagesProps) {
  const parsed = parseOptionContent(value || '')

  if (!parsed.text && !parsed.imageUrls.length && !parsed.pendingImageCount) {
    return null
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, ...style }}>
      {parsed.text && (
        <Text
          strong={strong}
          style={{
            fontSize,
            whiteSpace: 'pre-wrap',
            ...textStyle,
          }}
        >
          {parsed.text}
        </Text>
      )}

      {parsed.imageUrls.map((imageUrl, index) => (
        <img
          key={`${imageUrl}-${index}`}
          src={imageUrl}
          alt={imageAlt}
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
  )
}
