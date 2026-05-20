<template>
  <nav class="navbar">
    <div class="nav-container">
      <div class="nav-brand">
        <router-link to="/" class="brand-link">
          <el-icon><Film /></el-icon>
          <span>AI电影推荐</span>
        </router-link>
      </div>
      
      <div class="nav-menu">
        <router-link to="/" class="nav-link">
          <el-icon><HomeFilled /></el-icon>
          <span>首页</span>
        </router-link>
        <router-link to="/movies" class="nav-link">
          <el-icon><Search /></el-icon>
          <span>发现电影</span>
        </router-link>
        <router-link to="/chat" class="nav-link">
          <el-icon><ChatDotRound /></el-icon>
          <span>智能助手</span>
        </router-link>
        <router-link to="/profile" class="nav-link">
          <el-icon><User /></el-icon>
          <span>我的</span>
        </router-link>
      </div>
      
      <div class="nav-user">
        <el-dropdown @command="handleCommand">
          <div class="user-info">
            <el-avatar :size="32" :icon="UserFilled" />
            <span>{{ userStore.user?.username || '用户' }}</span>
            <el-icon><ArrowDown /></el-icon>
          </div>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="profile">个人资料</el-dropdown-item>
              <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </div>
  </nav>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { useUserStore } from '../stores/user'
import { Film, HomeFilled, Search, ChatDotRound, User, UserFilled, ArrowDown } from '@element-plus/icons-vue'

const router = useRouter()
const userStore = useUserStore()

const handleCommand = (command) => {
  if (command === 'profile') {
    router.push('/profile')
  } else if (command === 'logout') {
    userStore.logout()
    router.push('/login')
  }
}
</script>

<style scoped>
.navbar {
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  box-shadow: 0 2px 20px rgba(0, 0, 0, 0.1);
  position: sticky;
  top: 0;
  z-index: 1000;
}

.nav-container {
  max-width: 1400px;
  margin: 0 auto;
  padding: 0 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 64px;
}

.brand-link {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 20px;
  font-weight: bold;
  color: #667eea;
  text-decoration: none;
}

.nav-menu {
  display: flex;
  gap: 32px;
}

.nav-link {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #333;
  text-decoration: none;
  padding: 8px 12px;
  border-radius: 8px;
  transition: all 0.3s;
}

.nav-link:hover,
.nav-link.router-link-active {
  background: #667eea;
  color: white;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 4px 12px;
  border-radius: 20px;
  transition: background 0.3s;
}

.user-info:hover {
  background: #f0f0f0;
}
</style>