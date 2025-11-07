<template>
  <div class="app-shell">
    <header class="app-shell__header">
      <h1>RAG 论文助手</h1>
      <p class="app-shell__subtitle">一站式完成论文查询与爬取，界面简洁、操作高效。</p>
    </header>

    <main class="app-shell__main">
      <RouterView />
    </main>

    <footer class="app-shell__footer">
      <span>Powered by Vue 3 + Vite · 专注两项关键能力</span>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { RouterView } from 'vue-router';
</script>
