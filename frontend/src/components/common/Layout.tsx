/**
 * 页面布局组件
 *
 * [INPUT]: 依赖 antd Layout 组件
 * [OUTPUT]: 对外提供 Layout 组件
 * [POS]: frontend/src/components/common 的布局组件
 * [PROTOCOL]: 变更时更新此头部,然后检查 CLAUDE.md
 */
import { useState } from 'react'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { Layout as AntLayout, Menu, Typography } from 'antd'
import {
  ReadOutlined,
  FileTextOutlined,
  HomeOutlined,
  UploadOutlined,
} from '@ant-design/icons'

const { Header, Sider, Content } = AntLayout
const { Title } = Typography

const menuItems = [
  {
    key: '/',
    icon: <HomeOutlined />,
    label: '首页',
  },
  {
    key: '/import',
    icon: <UploadOutlined />,
    label: '试卷导入',
  },
  {
    key: '/reading',
    icon: <ReadOutlined />,
    label: '阅读CD篇',
  },
  {
    key: '/handout',
    icon: <FileTextOutlined />,
    label: '讲义转换',
  },
]

export function Layout() {
  const [collapsed, setCollapsed] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()

  const handleMenuClick = ({ key }: { key: string }) => {
    navigate(key)
  }

  // 获取当前选中的菜单项
  const getSelectedKey = () => {
    const path = location.pathname
    // 处理详情页路由
    if (path.startsWith('/reading/') && path !== '/reading') {
      return '/reading'
    }
    return path
  }

  return (
    <AntLayout style={{ height: '100vh', overflow: 'hidden' }}>
      {/* 侧边栏 - 固定不滚动 */}
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        style={{
          background: '#001529',
          height: '100vh',
          position: 'fixed',
          left: 0,
          top: 0,
          bottom: 0,
          overflow: 'auto',
        }}
      >
        <div
          style={{
            height: 64,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <Title
            level={4}
            style={{
              color: '#fff',
              margin: 0,
              fontSize: collapsed ? 14 : 16,
              whiteSpace: 'nowrap',
              overflow: 'hidden',
            }}
          >
            {collapsed ? '教研' : '中考英语教研'}
          </Title>
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[getSelectedKey()]}
          items={menuItems}
          onClick={handleMenuClick}
        />
      </Sider>

      {/* 右侧内容区 - 独立滚动 */}
      <AntLayout style={{
        marginLeft: collapsed ? 80 : 200,
        transition: 'margin-left 0.2s',
        height: '100vh',
        overflow: 'hidden',
      }}>
        {/* 顶部Header - 固定 */}
        <Header
          style={{
            padding: '0 24px',
            background: '#fff',
            borderBottom: '1px solid #f0f0f0',
            position: 'sticky',
            top: 0,
            zIndex: 10,
          }}
        >
          <Title level={4} style={{ margin: '16px 0' }}>
            北京中考英语教研资料系统
          </Title>
        </Header>

        {/* 内容区 - 可滚动 */}
        <Content
          style={{
            margin: 0,
            padding: '20px 24px',
            background: '#fff',
            height: 'calc(100vh - 64px)',
            overflow: 'auto',
          }}
        >
          <Outlet />
        </Content>
      </AntLayout>
    </AntLayout>
  )
}
