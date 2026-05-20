import { defineStore } from 'pinia'
import { ref } from 'vue'
import { userAPI } from '../api'

export const useUserStore = defineStore('user', () => {
  const user = ref(null)
  const token = ref(localStorage.getItem('access_token') || null)
  const isAuthenticated = ref(!!token.value)

  const setUser = (userData) => {
    user.value = userData
  }

  const setToken = (newToken) => {
    token.value = newToken
    isAuthenticated.value = !!newToken
    if (newToken) {
      localStorage.setItem('access_token', newToken)
    } else {
      localStorage.removeItem('access_token')
      localStorage.removeItem('user')
    }
  }

  const login = async (credentials) => {
    const response = await userAPI.login(credentials)
    setToken(response.access_token)
    setUser(response.user)
    localStorage.setItem('user', JSON.stringify(response.user))
    return response
  }

  const register = async (userData) => {
    const response = await userAPI.register(userData)
    setToken(response.access_token)
    setUser(response.user)
    localStorage.setItem('user', JSON.stringify(response.user))
    return response
  }

  const logout = () => {
    setToken(null)
    setUser(null)
  }

  const fetchUserInfo = async () => {
    if (isAuthenticated.value) {
      try {
        const response = await userAPI.getMe()
        setUser(response.user)
        localStorage.setItem('user', JSON.stringify(response.user))
      } catch (error) {
        console.error('获取用户信息失败', error)
        logout()
      }
    }
  }

  // 恢复用户信息
  const restoreUser = () => {
    const storedUser = localStorage.getItem('user')
    if (storedUser && token.value) {
      user.value = JSON.parse(storedUser)
      isAuthenticated.value = true
    }
  }

  return {
    user,
    token,
    isAuthenticated,
    login,
    register,
    logout,
    fetchUserInfo,
    restoreUser,
    setUser,
    setToken
  }
})