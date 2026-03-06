/**
 * API服务
 */
import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 180000,  // 3分钟,因为LLM解析和主题提炼需要时间
  headers: {
    'Content-Type': 'application/json',
  },
})

// 响应拦截器
api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Error:', error)
    return Promise.reject(error)
  }
)

export default api
