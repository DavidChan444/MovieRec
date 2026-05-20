<template>
  <div class="movies-page">
    <div class="container">
      <div class="search-header">
        <h1>发现电影</h1>
        <div class="search-bar">
          <el-input
            v-model="searchQuery"
            placeholder="搜索电影..."
            :prefix-icon="Search"
            size="large"
            @keyup.enter="handleSearch"
          >
            <template #append>
              <el-button @click="handleSearch">搜索</el-button>
            </template>
          </el-input>
        </div>
      </div>

      <div v-loading="loading" class="movies-grid">
        <MovieCard
          v-for="movie in movies"
          :key="movie.movie_id || movie.id"
          :movie="movie"
        />
      </div>

      <div v-if="!loading && movies.length === 0" class="empty-state">
        <el-empty description="暂无电影数据" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { Search } from '@element-plus/icons-vue'
import { movieAPI } from '../api'
import MovieCard from '../components/MovieCard.vue'

const route = useRoute()
const searchQuery = ref('')
const movies = ref([])
const loading = ref(false)

const handleSearch = async () => {
  if (!searchQuery.value.trim()) return
  
  loading.value = true
  try {
    const params = { title: searchQuery.value, limit: 50 }
    movies.value = await movieAPI.search(params)
  } catch (error) {
    console.error('搜索失败', error)
    movies.value = []
  } finally {
    loading.value = false
  }
}

const loadTrending = async () => {
  loading.value = true
  try {
    movies.value = await movieAPI.getTrending(50)
  } catch (error) {
    console.error('加载失败', error)
    movies.value = []
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  const q = route.query.q
  if (q) {
    searchQuery.value = q
    handleSearch()
  } else {
    loadTrending()
  }
})
</script>

<style scoped>
.movies-page {
  padding: 40px 0;
  min-height: calc(100vh - 64px);
  background: #f5f5f5;
}

.search-header {
  text-align: center;
  margin-bottom: 40px;
}

.search-header h1 {
  font-size: 32px;
  margin-bottom: 24px;
}

.search-bar {
  max-width: 600px;
  margin: 0 auto;
}

.movies-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 24px;
}

.empty-state {
  text-align: center;
  padding: 60px 0;
}
</style>