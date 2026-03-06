/**
 * 页面布局组件
 */
import { useState } from 'react'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { Layout as AntLayout, Menu, Typography } from 'antd'
import {
  ReadOutlined,
  BookOutlined,
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
    label: '阅读C/D篇',
  },
  {
    key: '/vocabulary',
    icon: <BookOutlined />,
    label: '高频词汇',
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
    <AntLayout style={{ minHeight: '100vh' }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        style={{ background: '#001529' }}
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
      <AntLayout>
        <Header
          style={{
            padding: '0 24px',
            background: '#fff',
            borderBottom: '1px solid #f0f0f0',
          }}
        >
          <Title level={4} style={{ margin: '16px 0' }}>
            北京中考英语教研资料系统
          </Title>
        </Header>
        <Content
          style={{
            margin: '24px',
            padding: '24px',
            background: '#fff',
            borderRadius: '8px',
            minHeight: 'calc(100vh - 64px - 48px - 48px)',
          }}
        >
          <Outlet />
        </Content>
      </AntLayout>
    </AntLayout>
  )
}
