<template>
  <div class="movie-card" @click="goToDetail">
    <div class="movie-poster">
      <img v-if="!imageError" :src="posterUrl" :alt="movie.title" @error="handleImageError" />
      <div v-else class="no-poster">暂无封面</div>
      <div class="movie-rating" v-if="movie.rating">
        <el-rate :model-value="movie.rating / 2" disabled show-score text-color="#ff9900" />
      </div>
      <!-- Hover action buttons -->
      <div class="movie-actions" @click.stop>
        <button
          :class="['action-btn', 'like-btn', { active: isLiked }]"
          @click="toggleLike"
          :title="isLiked ? '已点赞' : '点赞'"
        >
          <el-icon><StarFilled v-if="isLiked" /><Star v-else /></el-icon>
        </button>
        <button
          :class="['action-btn', 'dislike-btn', { active: isDisliked }]"
          @click="toggleDislike"
          title="不感兴趣"
        >
          <el-icon><CircleCloseFilled v-if="isDisliked" /><CircleClose v-else /></el-icon>
        </button>
        <button
          :class="['action-btn', 'watch-btn', { active: isWatched }]"
          @click="toggleWatched"
          :title="isWatched ? '已看过' : '看过'"
        >
          <el-icon><View v-if="isWatched" /><View v-else /></el-icon>
        </button>
      </div>
    </div>
    <div class="movie-info">
      <h3 class="movie-title">{{ movie.title || '未知电影' }}</h3>
      <div class="movie-meta">
        <span class="year">{{ displayYear }}</span>
        <span class="genres">{{ displayGenres }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Star, StarFilled, CircleClose, CircleCloseFilled, View } from '@element-plus/icons-vue'
import { userAPI } from '../api'

const props = defineProps({
  movie: {
    type: Object,
    required: true
  },
  initialLiked: {
    type: Boolean,
    default: false
  },
  initialWatched: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['unliked', 'unwatched'])

const router = useRouter()

const imageError = ref(false)
const isLiked = ref(props.initialLiked)
const isDisliked = ref(false)
const isWatched = ref(props.initialWatched)

// Handle both API formats:
// MovieResponse: { poster_url, genre, year, plot, director, cast, duration }
// Movie.to_dict(): { poster, genres, release_date, summary, directors, actors, runtime }
const posterUrl = computed(() => {
  return props.movie.poster_url || props.movie.poster || 'https://via.placeholder.com/300x450?text=No+Poster'
})

const displayYear = computed(() => {
  if (props.movie.year) return props.movie.year
  if (props.movie.release_date) {
    const match = props.movie.release_date.match(/(\d{4})/)
    if (match) return match[1]
  }
  return 'N/A'
})

const displayGenres = computed(() => {
  // Both formats store genres as comma-separated string
  const genreStr = props.movie.genre || props.movie.genres || ''
  if (!genreStr) return ''
  return genreStr.split(',').map(g => g.trim()).filter(Boolean).slice(0, 2).join(' / ')
})

const movieIdStr = computed(() => {
  return String(props.movie.movie_id || props.movie.id || '')
})

const handleImageError = () => {
  imageError.value = true
}

const goToDetail = () => {
  router.push(`/movie/${props.movie.id}`)
}

const toggleLike = async () => {
  const wasLiked = isLiked.value
  isLiked.value = !wasLiked
  try {
    await userAPI.recordInteraction({
      movie_id: movieIdStr.value,
      interaction_type: wasLiked ? 'cancel_like' : 'like'
    })
    ElMessage.success(wasLiked ? '已取消点赞' : '已点赞')
    if (wasLiked) {
      emit('unliked', movieIdStr.value)
    }
  } catch (error) {
    isLiked.value = wasLiked
    console.error('点赞操作失败', error)
  }
}

const toggleDislike = async () => {
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
  }
}

const toggleWatched = async () => {
  const wasWatched = isWatched.value
  isWatched.value = !wasWatched
  try {
    await userAPI.recordInteraction({
      movie_id: movieIdStr.value,
      interaction_type: wasWatched ? 'cancel_view' : 'view'
    })
    ElMessage.success(wasWatched ? '已取消看过' : '已标记为看过，后续不再推荐')
    if (wasWatched) {
      emit('unwatched', movieIdStr.value)
    }
  } catch (error) {
    isWatched.value = wasWatched
    console.error('标记看过失败', error)
  }
}
</script>

<style scoped>
.movie-card {
  background: white;
  border-radius: 12px;
  overflow: hidden;
  cursor: pointer;
  transition: transform 0.3s, box-shadow 0.3s;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.movie-card:hover {
  transform: translateY(-8px);
  box-shadow: 0 12px 24px rgba(0, 0, 0, 0.2);
}

.movie-poster {
  position: relative;
  aspect-ratio: 2/3;
  overflow: hidden;
}

.movie-poster img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.3s;
}

.no-poster {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #e0e0e0 0%, #c0c0c0 100%);
  color: #999;
  font-size: 14px;
  font-weight: 500;
}

.movie-card:hover .movie-poster img {
  transform: scale(1.05);
}

.movie-rating {
  position: absolute;
  bottom: 8px;
  left: 8px;
  right: 8px;
  background: rgba(0, 0, 0, 0.7);
  padding: 4px 8px;
  border-radius: 8px;
  backdrop-filter: blur(4px);
}

.movie-actions {
  position: absolute;
  top: 8px;
  right: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  opacity: 0;
  transform: translateX(8px);
  transition: opacity 0.3s, transform 0.3s;
}

.movie-card:hover .movie-actions {
  opacity: 1;
  transform: translateX(0);
}

.action-btn {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: none;
  background: rgba(0, 0, 0, 0.65);
  color: white;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  transition: all 0.2s;
  backdrop-filter: blur(4px);
}

.action-btn:hover {
  background: rgba(0, 0, 0, 0.85);
  transform: scale(1.1);
}

.action-btn.active {
  background: rgba(102, 126, 234, 0.85);
}

.like-btn.active {
  background: rgba(245, 87, 83, 0.85);
}

.watch-btn.active {
  background: rgba(103, 194, 58, 0.85);
}

.movie-info {
  padding: 12px;
}

.movie-title {
  font-size: 14px;
  font-weight: 600;
  margin: 0 0 8px 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.movie-meta {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #999;
}

.genres {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
