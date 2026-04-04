/**
 * 已生成试卷列表组件
 *
 * [INPUT]: 依赖 antd List/Checkbox/Badge/Popconfirm/Button, @ant-design/icons, PaperHandoutStatus
 * [OUTPUT]: 对外提供 GeneratedPaperList 组件
 * [POS]: frontend/src/components/handout 的已生成试卷列表，支持勾选和撤回
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */

import { useMemo } from 'react'
import { Badge, Button, Checkbox, Empty, List, Popconfirm, Space, Typography } from 'antd'
import { CheckCircleOutlined, UndoOutlined } from '@ant-design/icons'
import type { PaperHandoutStatus } from '@/types'

const { Text } = Typography

interface GeneratedPaperListProps {
  papers: PaperHandoutStatus[]
  checkedIds: number[]
  onCheckedChange: (ids: number[]) => void
  onRevoke?: (paperId: number) => void
}

export function GeneratedPaperList({ papers, checkedIds, onCheckedChange, onRevoke }: GeneratedPaperListProps) {
  const allIds = useMemo(() => papers.map((p) => p.id), [papers])

  const allChecked = allIds.length > 0 && allIds.every((id) => checkedIds.includes(id))
  const someChecked = checkedIds.length > 0 && !allChecked

  const handleToggleAll = () => {
    onCheckedChange(allChecked ? [] : [...allIds])
  }

  const handleToggle = (id: number) => {
    onCheckedChange(
      checkedIds.includes(id)
        ? checkedIds.filter((i) => i !== id)
        : [...checkedIds, id]
    )
  }

  if (papers.length === 0) {
    return <Empty description="暂无已生成记录" image={Empty.PRESENTED_IMAGE_SIMPLE} />
  }

  return (
    <div>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          padding: '8px 12px',
          borderBottom: '1px solid #f0f0f0',
          background: '#fafafa',
        }}
      >
        <Checkbox
          indeterminate={someChecked}
          checked={allChecked}
          onChange={handleToggleAll}
        >
          <Text strong>全选</Text>
          <Badge
            count={checkedIds.length}
            size="small"
            style={{ marginLeft: 8 }}
          />
        </Checkbox>
      </div>

      <List
        dataSource={papers}
        style={{ overflow: 'auto', maxHeight: 'calc(100% - 44px)' }}
        renderItem={(paper) => {
          const checked = checkedIds.includes(paper.id)
          return (
            <List.Item
              style={{
                padding: '8px 12px',
                cursor: 'pointer',
                background: checked ? '#e6f7ff' : undefined,
                borderLeft: checked ? '3px solid #1890ff' : '3px solid transparent',
                transition: 'all 0.2s',
              }}
              onClick={() => handleToggle(paper.id)}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%' }}>
                <Checkbox checked={checked} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                    <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 12 }} />
                    <Text ellipsis style={{ fontSize: 13 }}>
                      {paper.filename}
                    </Text>
                  </div>
                  <Space size={4} style={{ marginTop: 2 }}>
                    {paper.year && <Text type="secondary" style={{ fontSize: 11 }}>{paper.year}</Text>}
                    {paper.region && <Text type="secondary" style={{ fontSize: 11 }}>{paper.region}</Text>}
                    {paper.exam_type && <Text type="secondary" style={{ fontSize: 11 }}>{paper.exam_type}</Text>}
                  </Space>
                </div>
                {onRevoke && (
                  <Popconfirm
                    title="确定撤回该记录？"
                    description="撤回后该试卷将回到「未生成」列表"
                    onConfirm={() => onRevoke(paper.id)}
                    okText="确定"
                    cancelText="取消"
                  >
                    <Button
                      size="small"
                      type="link"
                      danger
                      icon={<UndoOutlined />}
                      onClick={(e) => e.stopPropagation()}
                    >
                      撤回
                    </Button>
                  </Popconfirm>
                )}
              </div>
            </List.Item>
          )
        }}
      />
    </div>
  )
}
