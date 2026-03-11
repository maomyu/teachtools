/**
 * PDF 导出工具函数
 *
 * [INPUT]: 依赖 html2canvas、jspdf、antd message
 * [OUTPUT]: 对外提供 exportToPDF 函数
 * [POS]: frontend/src/utils 的 PDF 导出工具
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */
import html2canvas from 'html2canvas'
import jsPDF from 'jspdf'
import { message } from 'antd'

// ============================================================================
//  常量定义
// ============================================================================

// A4 尺寸（单位：mm）
const A4_WIDTH_MM = 210
const A4_HEIGHT_MM = 297

// DPI 转换系数（96 DPI 下 1mm ≈ 3.78px）
const MM_TO_PX = 3.78

// A4 像素尺寸
const A4_WIDTH_PX = A4_WIDTH_MM * MM_TO_PX   // ~794px
const A4_HEIGHT_PX = A4_HEIGHT_MM * MM_TO_PX  // ~1123px

// Canvas 缩放比例（2x 用于高清）
const CANVAS_SCALE = 2

// ============================================================================
//  主函数：将 DOM 元素导出为 PDF
// ============================================================================

/**
 * 将讲义容器导出为 PDF 文件
 *
 * 核心逻辑：
 * 1. 遍历每个 .handout-page 元素（已在 React 层面按 A4 分好页）
 * 2. 生成高清 canvas
 * 3. 每页直接添加到 PDF，保持原有分页
 */
export async function exportToPDF(
  container: HTMLElement,
  filename: string
): Promise<void> {
  message.loading('正在准备 PDF...', 0)

  try {
    const pages = container.querySelectorAll('.handout-page')
    const totalPages = pages.length

    if (totalPages === 0) {
      message.destroy()
      throw new Error('未找到可导出的页面')
    }

    // 创建 PDF（A4 尺寸）
    const pdf = new jsPDF({
      orientation: 'portrait',
      unit: 'mm',
      format: 'a4',
      compress: true,
    })

    for (let i = 0; i < totalPages; i++) {
      const page = pages[i] as HTMLElement

      // 更新进度提示
      message.destroy()
      message.loading(`正在处理第 ${i + 1}/${totalPages} 页...`, 0)

      // 生成当前页的 canvas
      const canvas = await html2canvas(page, {
        scale: CANVAS_SCALE,
        useCORS: true,
        allowTaint: true,
        logging: false,
        backgroundColor: '#ffffff',
        width: A4_WIDTH_PX,
        height: A4_HEIGHT_PX,
        scrollX: 0,
        scrollY: 0,
      })

      // 添加新页面（第一页之后）
      if (i > 0) {
        pdf.addPage()
      }

      // 直接使用 A4 尺寸添加图片
      const imgData = canvas.toDataURL('image/jpeg', 0.95)
      pdf.addImage(
        imgData,
        'JPEG',
        0,
        0,
        A4_WIDTH_MM,
        A4_HEIGHT_MM
      )
    }

    // 保存 PDF
    pdf.save(`${filename}.pdf`)

    message.destroy()
    message.success(`PDF 导出成功（共 ${totalPages} 页）`)
  } catch (error) {
    console.error('PDF 导出失败:', error)
    message.destroy()
    message.error('PDF 导出失败，请重试')
  }
}
