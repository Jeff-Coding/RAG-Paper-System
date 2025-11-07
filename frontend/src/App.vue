<template>
  <div class="app-shell">
    <header class="app-shell__header">
      <h1>RAG Paper Console</h1>
      <p class="app-shell__subtitle">Interact with your retrieval pipeline and monitor crawls.</p>
    </header>

    <main class="app-shell__main">
      <RouterView />
    </main>

    <footer class="app-shell__footer">
      <span>Ready for future modules · Built with Vue 3 + Vite</span>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { RouterView } from 'vue-router';
</script>
