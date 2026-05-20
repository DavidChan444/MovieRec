import axios from 'axios'
import { ElMessage } from 'element-plus'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// 请求拦截器
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器
api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (error.response) {
      const message = error.response.data?.detail || error.message
      ElMessage.error(message)
      
      // 401 未授权，跳转到登录页
      if (error.response.status === 401) {
        localStorage.removeItem('access_token')
        localStorage.removeItem('user')
        window.location.href = '/login'
      }
    } else {
      ElMessage.error('网络错误，请检查连接')
    }
    return Promise.reject(error)
  }
)

// 用户相关API
export const userAPI = {
  register: (data) => api.post('/users/register', data),
  login: (data) => api.post('/users/login', data),
  getMe: () => api.get('/users/me'),
  updateMe: (data) => api.put('/users/me', data),
  getPreferences: () => api.get('/users/preferences'),
  getInteractions: (limit = 50) => api.get('/users/interactions', { params: { limit } }),
  recordInteraction: (data) => api.post('/users/interactions', data),
  createReview: (data) => api.post('/users/reviews', data),
  getRecommendations: (query = '', limit = 10) => 
    api.get('/users/recommendations', { params: { query, limit } }),
  deleteAccount: () => api.delete('/users/account'),
  getInteractionMovies: (interactionType = null, limit = 50, offset = 0) =>
    api.get('/users/interactions/movies', { params: { interaction_type: interactionType, limit, offset } }),
}

// 电影相关API
export const movieAPI = {
  search: (params) => api.get('/movies/search', { params }),
  getTrending: (limit = 20) => api.get('/movies/trending', { params: { limit } }),
  getById: (movieId) => api.get(`/movies/${movieId}`),
  getSimilar: (movieId, limit = 10) => api.get(`/movies/${movieId}/similar`, { params: { limit } }),
}

// 聊天API
export const chatAPI = {
  chat: (data) => api.post('/chat/', data),

  getSessions: () => api.get('/chat/sessions'),
  getSessionMessages: (sessionId) => api.get(`/chat/sessions/${sessionId}/messages`),
  deleteSession: (sessionId) => api.delete(`/chat/sessions/${sessionId}`),
}

export default api