<template>
  <div class="home">
    <div class="hero-section">
      <div class="container">
        <h1 class="hero-title">发现你的下一部最爱电影</h1>
        <p class="hero-subtitle">基于AI的智能推荐系统，为你量身定制电影推荐</p>
        <div class="search-box">
          <el-input
            v-model="searchQuery"
            placeholder="描述你想看的电影类型或心情..."
            size="large"
            @keyup.enter="searchMovies"
          >
            <template #append>
              <el-button :icon="Search" @click="searchMovies">搜索</el-button>
            </template>
          </el-input>
        </div>
      </div>
    </div>

    <div class="content-section">
      <div class="container">
        <div class="section-header">
          <h2>为你推荐</h2>
          <el-button text @click="loadRecommendations">刷新</el-button>
        </div>
        
        <div v-loading="loadingRecommendations" class="movies-grid">
          <MovieCard
            v-for="movie in recommendations"
            :key="movie.movie_id || movie.id"
            :movie="movie"
          />
        </div>

        <div class="section-header" style="margin-top: 48px">
          <h2>热门电影</h2>
          <el-button text @click="loadTrending">刷新</el-button>
        </div>

        <div v-loading="loadingTrending" class="movies-grid">
          <MovieCard
            v-for="movie in trendingMovies"
            :key="movie.movie_id || movie.id"
            :movie="movie"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Search } from '@element-plus/icons-vue'
import { userAPI, movieAPI } from '../api'
import MovieCard from '../components/MovieCard.vue'
import { ElMessage } from 'element-plus'

const router = useRouter()
const searchQuery = ref('')
const recommendations = ref([])
const trendingMovies = ref([])
const loadingRecommendations = ref(false)
const loadingTrending = ref(false)

const loadRecommendations = async () => {
  loadingRecommendations.value = true
  try {
    const result = await userAPI.getRecommendations('', 20)
    recommendations.value = result.recommendations || []
  } catch (error) {
    console.error('加载推荐失败', error)
    recommendations.value = []
  } finally {
    loadingRecommendations.value = false
  }
}

const loadTrending = async () => {
  loadingTrending.value = true
  try {
    trendingMovies.value = await movieAPI.getTrending(12)
  } catch (error) {
    console.error('加载热门电影失败', error)
    trendingMovies.value = []
  } finally {
    loadingTrending.value = false
  }
}

const searchMovies = () => {
  if (searchQuery.value.trim()) {
    router.push(`/movies?q=${encodeURIComponent(searchQuery.value)}`)
  }
}

onMounted(() => {
  loadRecommendations()
  loadTrending()
})
</script>

<style scoped>
.hero-section {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 80px 0;
  text-align: center;
  color: white;
}

.hero-title {
  font-size: 48px;
  margin-bottom: 16px;
}

.hero-subtitle {
  font-size: 18px;
  opacity: 0.9;
  margin-bottom: 32px;
}

.search-box {
  max-width: 600px;
  margin: 0 auto;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.section-header h2 {
  font-size: 28px;
  font-weight: 600;
}

.movies-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 24px;
}

.content-section {
  padding: 48px 0;
  background: #f5f5f5;
}
</style>