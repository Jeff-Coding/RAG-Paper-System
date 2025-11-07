<template>
  <section class="card">
    <header class="card__header">
      <h2>Trigger crawl</h2>
      <p>Start ingesting new documents from a seed URL.</p>
    </header>

    <form class="stack" @submit.prevent="submit">
      <label class="field">
        <span class="field__label">Seed URL</span>
        <input
          v-model="seedUrl"
          type="url"
          name="seedUrl"
          placeholder="https://arxiv.org/list/cs.AI/recent"
          required
        />
      </label>

      <div class="actions">
        <button class="btn" type="submit" :disabled="isLoading || !seedUrl.trim().length">
          <span v-if="isLoading">Triggering…</span>
          <span v-else>Trigger crawl</span>
        </button>
      </div>
    </form>

    <p v-if="successMessage" class="alert alert--success">{{ successMessage }}</p>
    <p v-if="error" class="alert alert--error">{{ error }}</p>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import type { CrawlResponse } from '@/types/api';

const props = defineProps<{
  isLoading: boolean;
  result: CrawlResponse | null;
  error: string | null;
}>();

const emit = defineEmits<{
  submit: [seedUrl: string];
}>();

const seedUrl = ref('');
const isLoading = computed(() => props.isLoading);
const successMessage = computed(() => props.result?.message ?? props.result?.status ?? '');
const error = computed(() => props.error);

watch(
  () => props.result,
  (value) => {
    if (value) {
      seedUrl.value = '';
    }
  }
);

function submit() {
  const trimmed = seedUrl.value.trim();
  if (!trimmed) {
    return;
  }
  emit('submit', trimmed);
}
</script>
