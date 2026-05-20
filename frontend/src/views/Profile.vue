<template>
  <div class="profile-page">
    <div class="container">
      <div class="profile-header">
        <div class="avatar-section">
          <el-avatar :size="100" :icon="UserFilled" />
          <h2>{{ user?.username }}</h2>
          <p>{{ user?.email }}</p>
        </div>
      </div>

      <el-tabs v-model="activeTab">
        <el-tab-pane label="个人资料" name="info">
          <el-form :model="profileForm" label-width="100px">
            <el-form-item label="姓名">
              <el-input v-model="profileForm.full_name" placeholder="请输入姓名" />
            </el-form-item>
            <el-form-item label="出生年份">
              <el-input-number v-model="profileForm.birth_year" :min="1900" :max="2024" />
            </el-form-item>
            <el-form-item label="性别">
              <el-radio-group v-model="profileForm.gender">
                <el-radio label="男">男</el-radio>
                <el-radio label="女">女</el-radio>
                <el-radio label="保密">保密</el-radio>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="所在地">
              <el-input v-model="profileForm.location" placeholder="请输入所在地" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="updateProfile">保存修改</el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <el-tab-pane label="偏好分析" name="preferences">
          <div v-loading="loadingPreferences">
            <div v-if="preferences" class="preferences-stats">
              <h3>观影统计</h3>
              <el-descriptions :column="2" border>
                <el-descriptions-item label="总观影数">{{ behaviorStats?.total_movies_watched || 0 }}</el-descriptions-item>
                <el-descriptions-item label="点赞数">{{ behaviorStats?.total_likes || 0 }}</el-descriptions-item>
                <el-descriptions-item label="不感兴趣数">{{ behaviorStats?.total_dislikes || 0 }}</el-descriptions-item>
                <el-descriptions-item label="总交互数">{{ behaviorStats?.total_interactions || 0 }}</el-descriptions-item>
                <el-descriptions-item label="置信度">{{ Math.round((preferences.confidence_score || 0) * 100) }}%</el-descriptions-item>
              </el-descriptions>

              <h3 style="margin-top: 24px">类型偏好</h3>
              <div v-if="genrePrefs && Object.keys(genrePrefs).length" class="genre-chart">
                <div v-for="(score, genre) in genrePrefs" :key="genre" class="genre-bar">
                  <span class="genre-name">{{ genre }}</span>
                  <el-progress :percentage="Math.round(score * 100)" :color="'#667eea'" />
                </div>
              </div>
              <el-empty v-else description="暂无类型偏好数据" :image-size="60" />

              <h3 style="margin-top: 24px">导演偏好</h3>
              <div v-if="directorPrefs && Object.keys(directorPrefs).length" class="genre-chart">
                <div v-for="(score, director) in directorPrefs" :key="director" class="genre-bar">
                  <span class="genre-name">{{ director }}</span>
                  <el-progress :percentage="Math.round(score * 100)" :color="'#409EFF'" />
                </div>
              </div>
              <el-empty v-else description="暂无导演偏好数据" :image-size="60" />

              <h3 style="margin-top: 24px">演员偏好</h3>
              <div v-if="actorPrefs && Object.keys(actorPrefs).length" class="genre-chart">
                <div v-for="(score, actor) in actorPrefs" :key="actor" class="genre-bar">
                  <span class="genre-name">{{ actor }}</span>
                  <el-progress :percentage="Math.round(score * 100)" :color="'#67C23A'" />
                </div>
              </div>
              <el-empty v-else description="暂无演员偏好数据" :image-size="60" />

              <h3 style="margin-top: 24px">评分偏好</h3>
              <el-descriptions v-if="ratingPrefs" :column="2" border>
                <el-descriptions-item label="偏好类型">{{ ratingLabel }}</el-descriptions-item>
                <el-descriptions-item label="平均评分">{{ ratingPrefs.avg_rating || 'N/A' }}</el-descriptions-item>
                <el-descriptions-item label="评分标准差">{{ ratingPrefs.std_rating || 'N/A' }}</el-descriptions-item>
                <el-descriptions-item label="最低接受评分">{{ ratingPrefs.min_acceptable || 'N/A' }}</el-descriptions-item>
              </el-descriptions>

              <h3 style="margin-top: 24px">推荐策略</h3>
              <el-descriptions v-if="strategy" :column="2" border>
                <el-descriptions-item label="主要方法">{{ strategyLabel }}</el-descriptions-item>
                <el-descriptions-item label="多样性等级">{{ diversityLabel }}</el-descriptions-item>
                <el-descriptions-item label="探索率">{{ Math.round((strategy.exploration_rate || 0) * 100) }}%</el-descriptions-item>
                <el-descriptions-item label="质量阈值">{{ strategy.quality_threshold || 'N/A' }}</el-descriptions-item>
              </el-descriptions>

              <h3 style="margin-top: 24px">活跃时段</h3>
              <div v-if="temporalPrefs" class="temporal-info">
                <el-tag v-for="hour in temporalPrefs.peak_hours" :key="hour" type="warning" style="margin-right: 8px">
                  {{ hour }}:00 - {{ hour + 1 }}:00
                </el-tag>
                <p style="margin-top: 8px; color: #999">
                  近7天活跃度: {{ temporalPrefs.recent_activity || 0 }} 次交互
                </p>
              </div>
              <el-empty v-else description="暂无活跃数据" :image-size="60" />
            </div>
            <el-empty v-else description="暂无偏好分析数据" />
          </div>
        </el-tab-pane>

        <el-tab-pane label="交互历史" name="interactions">
          <el-table :data="interactions" v-loading="loadingInteractions" style="width: 100%">
            <el-table-column prop="movie_id" label="电影ID" />
            <el-table-column prop="interaction_type" label="交互类型" />
            <el-table-column prop="interaction_time" label="时间">
              <template #default="{ row }">
                {{ new Date(row.interaction_time).toLocaleString() }}
              </template>
            </el-table-column>
            <el-table-column prop="duration" label="时长(秒)" />
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="点赞电影" name="liked">
          <div v-loading="loadingLiked">
            <div v-if="likedMovies.length > 0" class="movie-grid">
              <MovieCard
                v-for="movie in likedMovies"
                :key="movie.id || movie.movie_id"
                :movie="movie"
                :initial-liked="true"
                @unliked="handleUnliked"
              />
            </div>
            <el-empty v-else description="暂无点赞电影" :image-size="80" />
          </div>
        </el-tab-pane>

        <el-tab-pane label="看过电影" name="watched">
          <div v-loading="loadingWatched">
            <div v-if="watchedMovies.length > 0" class="movie-grid">
              <MovieCard
                v-for="movie in watchedMovies"
                :key="movie.id || movie.movie_id"
                :movie="movie"
                :initial-watched="true"
                @unwatched="handleUnwatched"
              />
            </div>
            <el-empty v-else description="暂无看过电影" :image-size="80" />
          </div>
        </el-tab-pane>

      </el-tabs>

      <div class="danger-zone">
        <el-divider />
        <el-alert title="危险操作区" type="error" :closable="false" />
        <el-button type="danger" @click="deleteAccount" style="margin-top: 16px">
          注销账户
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UserFilled } from '@element-plus/icons-vue'
import { userAPI } from '../api'
import { useUserStore } from '../stores/user'
import MovieCard from '../components/MovieCard.vue'

const router = useRouter()
const userStore = useUserStore()
const activeTab = ref('info')
const loadingPreferences = ref(false)
const loadingInteractions = ref(false)
const preferences = ref(null)
const behaviorStats = ref(null)
const interactions = ref([])
const likedMovies = ref([])
const watchedMovies = ref([])
const loadingLiked = ref(false)
const loadingWatched = ref(false)

const user = computed(() => userStore.user)

// Extract inner preferences from the nested response structure
const innerPrefs = computed(() => preferences.value?.preferences || {})

const genrePrefs = computed(() => innerPrefs.value?.genres || {})
const directorPrefs = computed(() => innerPrefs.value?.directors || {})
const actorPrefs = computed(() => innerPrefs.value?.actors || {})
const ratingPrefs = computed(() => innerPrefs.value?.ratings || null)
const temporalPrefs = computed(() => innerPrefs.value?.temporal || null)
const strategy = computed(() => preferences.value?.recommendation_strategy || null)

const ratingLabel = computed(() => {
  const map = {
    high_quality: '偏好高分', medium_high: '偏好中高分',
    medium: '中等偏好', diverse: '多样化'
  }
  return map[ratingPrefs.value?.preference] || ratingPrefs.value?.preference || 'N/A'
})

const strategyLabel = computed(() => {
  const map = {
    content_based: '基于内容', collaborative: '协同过滤',
    hybrid: '混合推荐'
  }
  return map[strategy.value?.primary_method] || strategy.value?.primary_method || 'N/A'
})

const diversityLabel = computed(() => {
  const map = { low: '低', medium: '中', high: '高' }
  return map[strategy.value?.diversity_level] || strategy.value?.diversity_level || 'N/A'
})

const profileForm = ref({
  full_name: userStore.user?.full_name || '',
  birth_year: userStore.user?.birth_year || null,
  gender: userStore.user?.gender || '',
  location: userStore.user?.location || ''
})

const updateProfile = async () => {
  try {
    await userAPI.updateMe(profileForm.value)
    ElMessage.success('资料更新成功')
    userStore.fetchUserInfo()
  } catch (error) {
    console.error('更新失败', error)
  }
}

const loadPreferences = async () => {
  loadingPreferences.value = true
  try {
    const result = await userAPI.getPreferences()
    preferences.value = result.preferences
    behaviorStats.value = result.behavior_stats
  } catch (error) {
    console.error('加载偏好失败', error)
  } finally {
    loadingPreferences.value = false
  }
}

const loadInteractions = async () => {
  loadingInteractions.value = true
  try {
    const result = await userAPI.getInteractions(50)
    interactions.value = result.interactions
  } catch (error) {
    console.error('加载交互历史失败', error)
  } finally {
    loadingInteractions.value = false
  }
}

const loadLikedMovies = async () => {
  loadingLiked.value = true
  try {
    const result = await userAPI.getInteractionMovies('like', 30)
    likedMovies.value = result.movies || []
  } catch (error) {
    console.error('加载点赞电影失败', error)
  } finally {
    loadingLiked.value = false
  }
}

const loadWatchedMovies = async () => {
  loadingWatched.value = true
  try {
    const result = await userAPI.getInteractionMovies('view', 30)
    watchedMovies.value = result.movies || []
  } catch (error) {
    console.error('加载看过电影失败', error)
  } finally {
    loadingWatched.value = false
  }
}

const handleUnliked = (movieId) => {
  likedMovies.value = likedMovies.value.filter(m => String(m.id || m.movie_id) !== String(movieId))
}

const handleUnwatched = (movieId) => {
  watchedMovies.value = watchedMovies.value.filter(m => String(m.id || m.movie_id) !== String(movieId))
}

watch(activeTab, (newTab) => {
  if (newTab === 'liked' && likedMovies.value.length === 0) loadLikedMovies()
  if (newTab === 'watched' && watchedMovies.value.length === 0) loadWatchedMovies()
})

const deleteAccount = async () => {
  try {
    await ElMessageBox.confirm('注销后账户将无法恢复，确定要注销吗？', '警告', {
      confirmButtonText: '确定注销',
      cancelButtonText: '取消',
      type: 'error'
    })
    
    await userAPI.deleteAccount()
    ElMessage.success('账户已注销')
    userStore.logout()
    router.push('/login')
  } catch (error) {
    if (error !== 'cancel') {
      console.error('注销失败', error)
    }
  }
}

onMounted(() => {
  loadPreferences()
  loadInteractions()
})
</script>

<style scoped>
.profile-page {
  min-height: calc(100vh - 64px);
  background: #f5f5f5;
  padding: 40px 0;
}

.profile-header {
  background: white;
  border-radius: 16px;
  padding: 40px;
  text-align: center;
  margin-bottom: 24px;
}

.avatar-section h2 {
  margin-top: 16px;
  margin-bottom: 8px;
}

.preferences-stats h3 {
  margin-bottom: 16px;
}

.genre-chart {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.genre-bar {
  display: flex;
  align-items: center;
  gap: 16px;
}

.genre-name {
  width: 100px;
  font-weight: 500;
}

.movie-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 20px;
  padding: 16px 0;
}

.danger-zone {
  margin-top: 32px;
}
</style>