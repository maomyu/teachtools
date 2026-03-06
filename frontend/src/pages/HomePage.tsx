/**
 * 首页
 */
import { Card, Row, Col, Statistic, Typography, Divider } from 'antd'
import {
  FileTextOutlined,
  ReadOutlined,
  BookOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons'

const { Title, Paragraph } = Typography

export function HomePage() {
  return (
    <div>
      <Title level={2}>欢迎使用北京中考英语教研资料系统</Title>
      <Paragraph>
        本系统将北京中考英语历年真题从"按套卷堆叠"升级为"按话题/考点组织"，
        帮助教师快速查找话题文章、提取高频词汇、生成讲义。
      </Paragraph>

      <Divider />

      <Row gutter={[16, 16]}>
        <Col span={6}>
          <Card>
            <Statistic
              title="试卷数量"
              value={1071}
              prefix={<FileTextOutlined />}
              valueStyle={{ color: '#1890ff' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="阅读文章"
              value={2142}
              prefix={<ReadOutlined />}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="高频词汇"
              value={5000}
              prefix={<BookOutlined />}
              valueStyle={{ color: '#faad14' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="话题分类"
              value={28}
              prefix={<CheckCircleOutlined />}
              valueStyle={{ color: '#722ed1' }}
            />
          </Card>
        </Col>
      </Row>

      <Divider />

      <Title level={3}>核心功能</Title>
      <Row gutter={[16, 16]}>
        <Col span={12}>
          <Card
            title="阅读C/D篇"
            extra={<ReadOutlined />}
            hoverable
          >
            <Paragraph>
              按话题分类浏览阅读C/D篇文章，支持高频词汇提取和原文定位。
            </Paragraph>
          </Card>
        </Col>
        <Col span={12}>
          <Card
            title="高频词汇"
            extra={<BookOutlined />}
            hoverable
          >
            <Paragraph>
              按话题统计高频词汇，每个词汇都有例句和出处，点击可定位到原文。
            </Paragraph>
          </Card>
        </Col>
      </Row>

      <Divider />

      <Title level={3}>数据范围</Title>
      <Paragraph>
        <ul>
          <li>时间范围：2022-2025年</li>
          <li>年级覆盖：初一、初二、初三</li>
          <li>考试类型：期中、期末、一模、二模</li>
          <li>区县覆盖：东城、西城、海淀、朝阳、丰台等16个区</li>
        </ul>
      </Paragraph>
    </div>
  )
}
