<template>
  <section class="card">
    <header class="card__header">
      <h2>Ask a question</h2>
      <p>Send a prompt to the retrieval pipeline and inspect the response.</p>
    </header>

    <form class="stack" @submit.prevent="submit">
      <label class="field">
        <span class="field__label">Question</span>
        <textarea
          v-model="query"
          name="question"
          rows="5"
          placeholder="What is the main contribution of the latest crawl?"
          required
        />
      </label>

      <div class="actions">
        <button class="btn" type="submit" :disabled="isLoading || !query.trim().length">
          <span v-if="isLoading">Asking…</span>
          <span v-else>Ask</span>
        </button>
      </div>
    </form>

    <p v-if="error" class="alert alert--error">{{ error }}</p>

    <div v-if="answer" class="result">
      <h3>Answer</h3>
      <p>{{ answer.answer }}</p>

      <ul v-if="answer.references?.length" class="result__references">
        <li v-for="ref in answer.references" :key="ref">
          <a :href="ref" target="_blank" rel="noopener">{{ ref }}</a>
        </li>
      </ul>

      <p v-if="answer.elapsed" class="result__meta">Answered in {{ answer.elapsed.toFixed(2) }}s</p>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import type { AskResponse } from '@/types/api';

const props = defineProps<{
  isLoading: boolean;
  answer: AskResponse | null;
  error: string | null;
}>();

const emit = defineEmits<{
  submit: [query: string];
}>();

const query = ref('');

const isLoading = computed(() => props.isLoading);
const answer = computed(() => props.answer);
const error = computed(() => props.error);

watch(
  () => props.answer,
  (value) => {
    if (value) {
      query.value = '';
    }
  }
);

function submit() {
  const trimmed = query.value.trim();
  if (!trimmed) {
    return;
  }
  emit('submit', trimmed);
}
</script>
