<template>
  <section class="card ask-card">
    <header class="card__header">
      <div class="card__title-group">
        <span class="card__eyebrow">智能查询</span>
        <h2>快速获取论文答案</h2>
      </div>
      <p>提出你的问题，系统会结合知识库返回摘要、结论及参考链接。</p>
    </header>

    <form class="stack" @submit.prevent="submit">
      <label class="field">
        <span class="field__label">问题描述</span>
        <textarea
          v-model="query"
          name="question"
          rows="6"
          placeholder="例如：Transformer 在长文本建模上的最新改进有哪些？"
          required
        />
      </label>

      <div class="ask-card__suggestions" role="list">
        <button
          v-for="item in suggestions"
          :key="item"
          type="button"
          class="chip"
          @click="applySuggestion(item)"
        >
          {{ item }}
        </button>
      </div>

      <div class="actions">
        <button class="btn" type="submit" :disabled="isLoading || !query.trim().length">
          <span v-if="isLoading">正在查询…</span>
          <span v-else>获取答案</span>
        </button>
      </div>
    </form>

    <p v-if="error" class="alert alert--error">{{ error }}</p>

    <div v-if="answer" class="result">
      <h3>答案概要</h3>
      <p class="result__content">{{ answer.answer }}</p>

      <div v-if="referenceEntries.length" class="result__references">
        <h4>参考链接</h4>
        <div class="result__reference-tags">
          <template v-for="(ref, index) in referenceEntries" :key="index">
            <a
              v-if="ref.href"
              :href="ref.href"
              target="_blank"
              rel="noopener"
              class="chip chip--link"
            >
              {{ ref.label }}
            </a>
            <span v-else class="chip">{{ ref.label }}</span>
          </template>
        </div>
      </div>

      <p v-if="answer.elapsed" class="result__meta">响应时间 {{ answer.elapsed.toFixed(2) }}s</p>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import type { AskResponse, ReferenceItem } from '@/types/api';

const props = defineProps<{
  isLoading: boolean;
  answer: AskResponse | null;
  error: string | null;
}>();

const emit = defineEmits<{
  submit: [query: string];
}>();

const query = ref('');
const suggestions = ['最新综述', '核心贡献', '实验结果亮点'];

const isLoading = computed(() => props.isLoading);
const answer = computed(() => props.answer);
const error = computed(() => props.error);
const referenceEntries = computed(() => {
  const items = answer.value?.references ?? [];
  return items.map((entry, index) => normalizeReference(entry, index));
});

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
  if (!trimmed || isLoading.value) {
    return;
  }
  emit('submit', trimmed);
}

function applySuggestion(text: string) {
  query.value = text;
}

function normalizeReference(entry: string | ReferenceItem, index: number) {
  if (typeof entry === 'string') {
    const trimmed = entry.trim();
    const href = /^https?:\/\//i.test(trimmed) ? trimmed : undefined;
    return {
      label: trimmed || `参考 ${index + 1}`,
      href
    };
  }

  const label = entry.title || entry.url || entry.source || `参考 ${index + 1}`;
  const href = entry.url && entry.url.trim().length ? entry.url : undefined;

  return { label, href };
}
</script>
