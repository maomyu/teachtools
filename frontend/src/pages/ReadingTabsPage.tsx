/**
 * 阅读模块Tab容器页
 *
 * [INPUT]: 依赖 antd Tabs 组件、VocabularyPage、ReadingContent
 * [OUTPUT]: 对外提供 ReadingTabsPage 组件
 * [POS]: frontend/src/pages 的Tab容器，整合高频词库和文章列表
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */
import { useState } from 'react'
import { Tabs } from 'antd'
import { BookOutlined, FileTextOutlined } from '@ant-design/icons'

import { VocabularyPage } from './VocabularyPage'
import { ReadingContent } from './ReadingContent'

export function ReadingTabsPage() {
  const [activeKey, setActiveKey] = useState('vocabulary')

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Tabs
        activeKey={activeKey}
        onChange={setActiveKey}
        type="card"
        size="large"
        tabBarStyle={{
          marginBottom: 0,
          paddingLeft: 16,
          background: '#fafafa',
        }}
        items={[
          {
            key: 'vocabulary',
            label: (
              <span style={{ padding: '0 8px' }}>
                <BookOutlined style={{ marginRight: 8 }} />
                高频词库
              </span>
            ),
            children: <VocabularyPage />,
          },
          {
            key: 'passages',
            label: (
              <span style={{ padding: '0 8px' }}>
                <FileTextOutlined style={{ marginRight: 8 }} />
                文章列表
              </span>
            ),
            children: <ReadingContent />,
          },
        ]}
        style={{ height: '100%' }}
      />
    </div>
  )
}
