<template>
  <div id="app">
    <NavBar v-if="userStore.isAuthenticated" />
    <router-view v-slot="{ Component }">
      <transition name="fade" mode="out-in">
        <component :is="Component" />
      </transition>
    </router-view>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import NavBar from './components/NavBar.vue'
import { useUserStore } from './stores/user'

const userStore = useUserStore()

onMounted(() => {
  userStore.restoreUser()
  userStore.fetchUserInfo()
})
</script>

<style>
#app {
  min-height: 100vh;
}
</style>