<template>
  <div class="chat-container">
    <div class="chat-sidebar">
      <div class="sidebar-header">
        <h3>🤖 AI智能助手</h3>
        <p>我可以帮你推荐电影</p>
      </div>
      <div class="sidebar-content">
        <!-- New chat button -->
        <button class="new-chat-btn" @click="startNewSession">
          <el-icon><Plus /></el-icon> 新对话
        </button>

        <!-- Session list -->
        <div class="session-list" v-if="sessions.length > 0">
          <h4>💬 历史对话</h4>
          <div
            v-for="session in sessions"
            :key="session.id"
            :class="['session-item', { active: session.id === currentSessionId }]"
            @click="loadSession(session.id)"
          >
            <div class="session-info">
              <span class="session-title">{{ session.title }}</span>
              <span class="session-time">{{ formatSessionTime(session.updated_at) }}</span>
            </div>
            <button class="delete-session-btn" @click.stop="handleDeleteSession(session.id)" title="删除">
              <el-icon><Close /></el-icon>
            </button>
          </div>
        </div>

        <!-- Suggestions -->
        <div class="suggestion-tips">
          <h4>✨ 你可以这样问：</h4>
          <ul>
            <li @click="sendSuggestion('推荐几部好看的科幻电影')">推荐几部好看的科幻电影</li>
            <li @click="sendSuggestion('最近有什么热门电影')">最近有什么热门电影</li>
            <li @click="sendSuggestion('我想看一部轻松搞笑的喜剧片')">我想看一部轻松搞笑的喜剧片</li>
            <li @click="sendSuggestion('有什么经典动作片推荐')">有什么经典动作片推荐</li>
            <li @click="sendSuggestion('推荐适合情侣看的爱情电影')">推荐适合情侣看的爱情电影</li>
            <li @click="sendSuggestion('有没有评分高的悬疑片')">有没有评分高的悬疑片</li>
          </ul>
        </div>

        <div class="info-tips">
          <div class="tip-item"> 支持自然语言对话</div>
          <div class="tip-item"> 智能分析观影偏好</div>
          <div class="tip-item"> 对话历史自动保存</div>
          <div class="tip-item"> 自适应个性化推荐</div>
        </div>
      </div>
    </div>

    <div class="chat-main">
      <div class="chat-messages" ref="messagesRef">
        <!-- Welcome message when empty -->
        <div v-if="messages.length === 0 && !loading" class="welcome-container">
          <div class="welcome-icon">🎬</div>
          <h2>AI电影推荐助手</h2>
          <p>告诉我你想看什么类型的电影，我会为你推荐最合适的！</p>
        </div>

        <div
          v-for="(msg, index) in messages"
          :key="index"
          :class="['message', msg.role]"
        >
          <div class="message-avatar">
            <div class="avatar" :class="msg.role">
              {{ msg.role === 'user' ? '👤' : '🤖' }}
            </div>
          </div>
          <div class="message-content">
            <div class="message-header">
              <span class="message-name">{{ msg.role === 'user' ? '我' : 'AI助手' }}</span>
              <span class="message-time">{{ formatTime(msg.time) }}</span>
            </div>
            <div class="message-text">{{ msg.content }}</div>

            <!-- 电影推荐卡片 -->
            <div v-if="msg.recommendations && msg.recommendations.length" class="message-recommendations">
              <div class="rec-title">为您推荐以下 {{ msg.recommendations.length }} 部电影：</div>
              <div class="rec-grid">
                <MovieCard
                  v-for="movie in msg.recommendations"
                  :key="movie.movie_id || movie.id"
                  :movie="movie"
                />
              </div>
              <div class="rec-reason-text" v-for="rec in msg.recommendations.filter(r => r.reason)" :key="'reason-'+rec.id">
                <span>《{{ rec.title }}》</span>：{{ rec.reason }}
              </div>
            </div>
          </div>
        </div>

        <!-- 加载动画 -->
        <div v-if="loading" class="message assistant">
          <div class="message-avatar">
            <div class="avatar assistant">🤖</div>
          </div>
          <div class="message-content">
            <div class="message-header">
              <span class="message-name">AI助手</span>
            </div>
            <div class="typing-indicator">
              <span></span>
              <span></span>
              <span></span>
            </div>
          </div>
        </div>
      </div>

      <div class="chat-input-area">
        <div class="input-container">
          <textarea
            v-model="inputMessage"
            :rows="3"
            placeholder="输入你的问题或电影需求... (Ctrl + Enter 发送)"
            @keyup.ctrl.enter="sendMessage"
            :disabled="loading"
            class="chat-textarea"
          ></textarea>
          <div class="input-actions">
            <div class="input-tips">💡 支持自然语言，告诉我你想看什么电影</div>
            <button
              class="send-btn"
              @click="sendMessage"
              :disabled="!inputMessage.trim() || loading"
            >
              发送
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Close } from '@element-plus/icons-vue'
import { chatAPI } from '../api'
import MovieCard from '../components/MovieCard.vue'

const router = useRouter()
const messagesRef = ref()
const inputMessage = ref('')
const loading = ref(false)
const sessions = ref([])
const currentSessionId = ref(null)

const messages = ref([])

// Load sessions on mount
onMounted(async () => {
  await loadSessions()
  scrollToBottom()
})

const loadSessions = async () => {
  try {
    const result = await chatAPI.getSessions()
    sessions.value = result.sessions || []
  } catch (error) {
    console.error('加载对话历史失败', error)
    sessions.value = []
  }
}

const startNewSession = () => {
  currentSessionId.value = null
  messages.value = []
  inputMessage.value = ''
}

const loadSession = async (sessionId) => {
  try {
    const result = await chatAPI.getSessionMessages(sessionId)
    currentSessionId.value = sessionId
    messages.value = (result.messages || []).map(m => ({
      role: m.role,
      content: m.content,
      recommendations: m.recommendations || [],
      time: new Date(m.created_at).getTime()
    }))
    await scrollToBottom()
  } catch (error) {
    console.error('加载对话失败', error)
    ElMessage.error('加载对话失败')
  }
}

const handleDeleteSession = async (sessionId) => {
  try {
    await ElMessageBox.confirm('确定要删除这个对话吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await chatAPI.deleteSession(sessionId)
    sessions.value = sessions.value.filter(s => s.id !== sessionId)
    if (currentSessionId.value === sessionId) {
      startNewSession()
    }
    ElMessage.success('对话已删除')
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除失败', error)
    }
  }
}

const formatTime = (timestamp) => {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  const now = new Date()
  const diff = now - date

  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`

  return `${date.getMonth() + 1}月${date.getDate()}日 ${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`
}

const formatSessionTime = (timestamp) => {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  const now = new Date()
  const diff = now - date

  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`
  if (diff < 604800000) return `${Math.floor(diff / 86400000)}天前`

  return `${date.getMonth() + 1}/${date.getDate()}`
}

const scrollToBottom = async () => {
  await nextTick()
  if (messagesRef.value) {
    messagesRef.value.scrollTop = messagesRef.value.scrollHeight
  }
}

const sendSuggestion = (suggestion) => {
  if (loading.value) return
  inputMessage.value = suggestion
  sendMessage()
}

const sendMessage = async () => {
  if (!inputMessage.value.trim() || loading.value) return

  const userMessage = inputMessage.value.trim()

  messages.value.push({
    role: 'user',
    content: userMessage,
    time: Date.now(),
    recommendations: []
  })

  inputMessage.value = ''
  await scrollToBottom()
  loading.value = true

  try {
    // Build history from current messages (exclude last user message)
    const history = messages.value
      .filter(m => m.role !== 'assistant' || m.recommendations?.length)
      .slice(-10)
      .map(m => ({
        role: m.role,
        content: m.content
      }))

    const response = await chatAPI.chat({
      message: userMessage,
      history: history.slice(0, -1),
      session_id: currentSessionId.value
    })

    // Update session ID from response
    if (response.session_id) {
      currentSessionId.value = response.session_id
    }

    messages.value.push({
      role: 'assistant',
      content: response.response,
      time: Date.now(),
      recommendations: response.recommendations || []
    })

    // Refresh session list
    await loadSessions()

    await scrollToBottom()

  } catch (error) {
    console.error('发送消息失败', error)
    messages.value.push({
      role: 'assistant',
      content: '抱歉，我遇到了一些问题，请稍后再试。',
      time: Date.now(),
      recommendations: []
    })
    await scrollToBottom()
  } finally {
    loading.value = false
  }
}

</script>

<style scoped>
.chat-container {
  display: flex;
  height: calc(100vh - 64px);
  background: #f5f5f5;
  overflow: hidden;
}

.chat-sidebar {
  width: 320px;
  background: white;
  border-right: 1px solid #e4e7ed;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}

.sidebar-header {
  padding: 24px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  text-align: center;
}

.sidebar-header h3 {
  font-size: 20px;
  margin-bottom: 8px;
}

.sidebar-header p {
  font-size: 14px;
  opacity: 0.9;
}

.sidebar-content {
  flex: 1;
  padding: 16px 20px;
}

.new-chat-btn {
  width: 100%;
  padding: 10px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  transition: opacity 0.2s;
  margin-bottom: 16px;
}

.new-chat-btn:hover {
  opacity: 0.9;
}

.session-list {
  margin-bottom: 16px;
}

.session-list h4 {
  font-size: 13px;
  color: #999;
  margin-bottom: 8px;
}

.session-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s;
  margin-bottom: 4px;
}

.session-item:hover {
  background: #f0f0f0;
}

.session-item.active {
  background: #e8edff;
  border: 1px solid #667eea;
}

.session-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.session-title {
  font-size: 13px;
  color: #333;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-time {
  font-size: 11px;
  color: #999;
}

.delete-session-btn {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  border: none;
  background: transparent;
  color: #999;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  transition: all 0.2s;
  flex-shrink: 0;
}

.delete-session-btn:hover {
  background: #f56c6c;
  color: white;
}

.suggestion-tips h4 {
  font-size: 13px;
  color: #666;
  margin-bottom: 8px;
}

.suggestion-tips ul {
  list-style: none;
  padding: 0;
  margin: 0;
}

.suggestion-tips li {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 10px;
  margin-bottom: 6px;
  background: #f5f7fa;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.3s;
  font-size: 13px;
  color: #333;
}

.suggestion-tips li:hover {
  background: #667eea;
  color: white;
  transform: translateX(4px);
}

.info-tips {
  margin-top: 16px;
}

.tip-item {
  padding: 6px 0;
  font-size: 12px;
  color: #999;
}

.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.welcome-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #999;
  text-align: center;
}

.welcome-icon {
  font-size: 64px;
  margin-bottom: 16px;
}

.welcome-container h2 {
  font-size: 24px;
  color: #666;
  margin-bottom: 8px;
}

.welcome-container p {
  font-size: 14px;
}

.message {
  display: flex;
  gap: 12px;
  margin-bottom: 24px;
  animation: slideIn 0.3s ease;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.message.user {
  flex-direction: row-reverse;
}

.message-content {
  flex: 1;
  max-width: 70%;
}

.avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  background: #f0f0f0;
  flex-shrink: 0;
}

.avatar.user {
  background: #667eea;
  color: white;
}

.avatar.assistant {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.message-header {
  display: flex;
  gap: 12px;
  align-items: baseline;
  margin-bottom: 6px;
}

.message.user .message-header {
  justify-content: flex-end;
}

.message-name {
  font-weight: 600;
  font-size: 14px;
  color: #333;
}

.message-time {
  font-size: 12px;
  color: #999;
}

.message-text {
  padding: 12px 16px;
  border-radius: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.message.user .message-text {
  background: #667eea;
  color: white;
}

.message.assistant .message-text {
  background: white;
  color: #333;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

.message-recommendations {
  margin-top: 16px;
}

.rec-title {
  margin-bottom: 12px;
  font-size: 14px;
  font-weight: 600;
  color: #333;
}

.rec-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 16px;
}

.rec-reason-text {
  font-size: 12px;
  color: #667eea;
  margin-top: 4px;
  line-height: 1.5;
}

.chat-input-area {
  border-top: 1px solid #e4e7ed;
  background: white;
  padding: 16px 20px;
}

.chat-textarea {
  width: 100%;
  border: 1px solid #dcdfe6;
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 14px;
  font-family: inherit;
  resize: vertical;
  transition: border-color 0.2s;
}

.chat-textarea:focus {
  outline: none;
  border-color: #667eea;
}

.input-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 12px;
}

.input-tips {
  font-size: 12px;
  color: #999;
}

.send-btn {
  padding: 8px 20px;
  background: #667eea;
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  transition: background 0.3s;
}

.send-btn:hover:not(:disabled) {
  background: #5a67d8;
}

.send-btn:disabled {
  background: #c0c4cc;
  cursor: not-allowed;
}

.typing-indicator {
  display: flex;
  gap: 4px;
  padding: 12px 16px;
  background: white;
  border-radius: 12px;
  display: inline-flex;
}

.typing-indicator span {
  width: 8px;
  height: 8px;
  background: #999;
  border-radius: 50%;
  animation: typing 1.4s infinite;
}

.typing-indicator span:nth-child(2) { animation-delay: 0.2s; }
.typing-indicator span:nth-child(3) { animation-delay: 0.4s; }

@keyframes typing {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
  30% { transform: translateY(-10px); opacity: 1; }
}

@media (max-width: 768px) {
  .chat-sidebar { display: none; }
  .message-content { max-width: 85%; }
  .rec-grid { grid-template-columns: 1fr; }
}
</style>
