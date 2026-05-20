<template>
  <div class="movie-detail" v-loading="loading">
    <div v-if="movie" class="container">
      <div class="movie-header">
        <div class="movie-poster">
          <img :src="posterUrl" :alt="movie.title" @error="handleImageError" />
        </div>
        <div class="movie-info">
          <h1>{{ movie.title }}</h1>
          <div class="meta-info">
            <span class="year">{{ displayYear }}年</span>
            <span class="rating">⭐ {{ movie.rating || '暂无评分' }}</span>
            <span class="duration" v-if="displayDuration">{{ displayDuration }}分钟</span>
          </div>
          <div class="genres">
            <el-tag v-for="genre in genreList" :key="genre" size="small" type="primary">{{ genre }}</el-tag>
          </div>
          <p class="plot">{{ displayPlot }}</p>
          <div class="meta-detail" v-if="movie.director || movie.directors">
            <span class="label">导演：</span>
            <span>{{ movie.director || movie.directors }}</span>
          </div>
          <div class="meta-detail" v-if="movie.cast || movie.actors">
            <span class="label">主演：</span>
            <span>{{ movie.cast || movie.actors }}</span>
          </div>
          <div class="actions">
            <el-button
              :type="isLiked ? 'danger' : 'default'"
              :icon="isLiked ? 'StarFilled' : 'Star'"
              @click="toggleLike"
              :loading="likeLoading"
            >
              {{ isLiked ? '已点赞' : '点赞' }}
            </el-button>
            <el-button
              type="info"
              @click="toggleDislike"
              :loading="dislikeLoading"
            >
              {{ isDisliked ? '已标记不感兴趣' : '不感兴趣' }}
            </el-button>
            <el-button
              :type="isWatched ? 'success' : 'default'"
              :icon="View"
              @click="toggleWatched"
              :loading="watchedLoading"
            >
              {{ isWatched ? '已看过' : '看过' }}
            </el-button>
            <el-button type="primary" @click="rateMovie">评价电影</el-button>
          </div>
        </div>
      </div>

      <div class="similar-section" v-if="similarMovies.length">
        <h2>相似电影推荐</h2>
        <div class="movies-grid">
          <MovieCard
            v-for="similar in similarMovies"
            :key="similar.id"
            :movie="similar"
          />
        </div>
      </div>
    </div>

    <!-- Empty state -->
    <div v-else-if="!loading" class="empty-state">
      <el-empty description="电影不存在">
        <el-button type="primary" @click="router.push('/movies')">去发现电影</el-button>
      </el-empty>
    </div>

    <!-- Rating dialog -->
    <el-dialog v-model="ratingDialogVisible" title="评价电影" width="400px">
      <div class="rating-form">
        <div class="rating-stars">
          <el-rate v-model="ratingValue" :texts="['很差', '较差', '还行', '推荐', '力荐']" show-text />
        </div>
        <el-input
          v-model="reviewText"
          type="textarea"
          :rows="4"
          placeholder="写下你的观后感..."
        />
      </div>
      <template #footer>
        <el-button @click="ratingDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitRating">提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { View } from '@element-plus/icons-vue'
import { movieAPI, userAPI } from '../api'
import MovieCard from '../components/MovieCard.vue'

const route = useRoute()
const router = useRouter()
const movie = ref(null)
const similarMovies = ref([])
const loading = ref(false)
const ratingDialogVisible = ref(false)
const ratingValue = ref(5)
const reviewText = ref('')
const isLiked = ref(false)
const isDisliked = ref(false)
const isWatched = ref(false)
const likeLoading = ref(false)
const dislikeLoading = ref(false)
const watchedLoading = ref(false)

// Field mapping helpers - handle both MovieResponse and Movie.to_dict() formats
const posterUrl = computed(() => {
  return movie.value?.poster_url || movie.value?.poster || 'https://via.placeholder.com/300x450'
})

const displayYear = computed(() => {
  if (!movie.value) return '未知'
  if (movie.value.year) return movie.value.year
  if (movie.value.release_date) {
    const match = movie.value.release_date.match(/(\d{4})/)
    if (match) return match[1]
  }
  return '未知'
})

const displayPlot = computed(() => {
  if (!movie.value) return '暂无简介'
  return movie.value.plot || movie.value.summary || '暂无简介'
})

const displayDuration = computed(() => {
  if (!movie.value) return null
  const dur = movie.value.duration || movie.value.runtime
  if (!dur) return null
  if (typeof dur === 'number') return dur
  const match = String(dur).match(/(\d+)/)
  return match ? parseInt(match[1]) : null
})

const genreList = computed(() => {
  if (!movie.value) return []
  // genre (MovieResponse) or genres (Movie.to_dict) - both are comma-separated strings
  const genreStr = movie.value.genre || movie.value.genres || ''
  return genreStr.split(',').map(g => g.trim()).filter(Boolean)
})

const movieIdStr = computed(() => {
  return String(movie.value?.movie_id || movie.value?.id || '')
})

const loadMovieDetail = async () => {
  loading.value = true
  try {
    movie.value = await movieAPI.getById(route.params.id)

    if (movie.value?.movie_id) {
      try {
        const similar = await movieAPI.getSimilar(movie.value.movie_id, 6)
        similarMovies.value = similar || []
      } catch (e) {
        console.error('加载相似电影失败', e)
        similarMovies.value = []
      }
    }
  } catch (error) {
    console.error('加载失败', error)
    if (error.response?.status === 404) {
      ElMessage.error('电影不存在')
    } else {
      ElMessage.error('加载电影详情失败')
    }
    movie.value = null
  } finally {
    loading.value = false
  }
}

const handleImageError = (e) => {
  e.target.src = 'https://via.placeholder.com/300x450'
}

const rateMovie = () => {
  ratingDialogVisible.value = true
}

const submitRating = async () => {
  try {
    await userAPI.createReview({
      movie_id: movieIdStr.value,
      rating: ratingValue.value * 2,
      review_text: reviewText.value
    })
    ElMessage.success('评价提交成功')
    ratingDialogVisible.value = false
    ratingValue.value = 5
    reviewText.value = ''
  } catch (error) {
    console.error('提交评价失败', error)
  }
}

const toggleLike = async () => {
  likeLoading.value = true
  const wasLiked = isLiked.value
  isLiked.value = !wasLiked
  try {
    await userAPI.recordInteraction({
      movie_id: movieIdStr.value,
      interaction_type: wasLiked ? 'cancel_like' : 'like'
    })
    ElMessage.success(wasLiked ? '已取消点赞' : '已点赞')
  } catch (error) {
    isLiked.value = wasLiked
    console.error('点赞操作失败', error)
  } finally {
    likeLoading.value = false
  }
}

const toggleDislike = async () => {
  dislikeLoading.value = true
  const wasDisliked = isDisliked.value
  isDisliked.value = !wasDisliked
  try {
    await userAPI.recordInteraction({
      movie_id: movieIdStr.value,
      interaction_type: wasDisliked ? 'cancel_dislike' : 'dislike'
    })
    ElMessage.success(wasDisliked ? '已取消不感兴趣' : '已标记为不感兴趣，将减少此类推荐')
  } catch (error) {
    isDisliked.value = wasDisliked
    console.error('操作失败', error)
  } finally {
    dislikeLoading.value = false
  }
}

const toggleWatched = async () => {
  watchedLoading.value = true
  const wasWatched = isWatched.value
  isWatched.value = !wasWatched
  try {
    await userAPI.recordInteraction({
      movie_id: movieIdStr.value,
      interaction_type: wasWatched ? 'cancel_view' : 'view'
    })
    ElMessage.success(wasWatched ? '已取消看过' : '已标记为看过，后续不再推荐')
  } catch (error) {
    isWatched.value = wasWatched
    console.error('标记看过失败', error)
  } finally {
    watchedLoading.value = false
  }
}

onMounted(() => {
  loadMovieDetail()
})
</script>

<style scoped>
.movie-detail {
  min-height: calc(100vh - 64px);
  background: #f5f5f5;
  padding: 40px 0;
}

.movie-header {
  display: grid;
  grid-template-columns: 300px 1fr;
  gap: 40px;
  background: white;
  padding: 30px;
  border-radius: 16px;
  margin-bottom: 40px;
}

.movie-poster img {
  width: 100%;
  border-radius: 12px;
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.1);
}

.movie-info h1 {
  font-size: 32px;
  margin-bottom: 16px;
}

.meta-info {
  display: flex;
  gap: 20px;
  margin-bottom: 16px;
  color: #666;
  flex-wrap: wrap;
}

.genres {
  display: flex;
  gap: 8px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.plot {
  line-height: 1.6;
  color: #333;
  margin-bottom: 16px;
}

.meta-detail {
  margin-bottom: 8px;
  font-size: 14px;
  color: #555;
}

.meta-detail .label {
  font-weight: 600;
  color: #333;
}

.actions {
  display: flex;
  gap: 12px;
  margin-top: 20px;
  flex-wrap: wrap;
}

.similar-section {
  background: white;
  padding: 30px;
  border-radius: 16px;
}

.similar-section h2 {
  margin-bottom: 24px;
}

.movies-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 20px;
}

.empty-state {
  text-align: center;
  padding: 80px 0;
}

.rating-form {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.rating-stars {
  text-align: center;
}
</style>
