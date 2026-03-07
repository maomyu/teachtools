/**
 * 文章详情页（含定位功能）
 *
 * 核心功能：
 * - 复用 PassageDetailContent 组件
 * - 提供独立页面路由
 */
import { useParams, useNavigate } from 'react-router-dom'
import { PassageDetailContent } from '@/components/vocabulary/PassageDetailContent'

export function PassageDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const handleBack = () => {
    navigate('/reading')
  }

  if (!id) {
    return <div>文章ID不存在</div>
  }

  return (
    <div style={{
      height: '100%',
      overflow: 'auto',
      padding: 16,
      background: '#fff',
    }}>
      <PassageDetailContent
        passageId={parseInt(id)}
        onBack={handleBack}
        showBackButton={true}
      />
    </div>
  )
}
