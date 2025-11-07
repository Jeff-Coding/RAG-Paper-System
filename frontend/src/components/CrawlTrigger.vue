<template>
  <section class="card crawl-card">
    <header class="card__header">
      <div class="card__title-group">
        <span class="card__eyebrow">数据爬取</span>
        <h2>批量收集论文</h2>
      </div>
      <p>输入想要获取的主题关键词，系统会自动从主流学术站点抓取并入库最新内容。</p>
    </header>

    <form class="stack" @submit.prevent="submit">
      <label class="field">
        <span class="field__label">检索主题</span>
        <textarea
          v-model="keyword"
          name="crawlQuery"
          rows="4"
          placeholder="例如：计算机视觉最新综述"
          required
        />
      </label>

      <div class="crawl-card__tips">
        <span>快速填入：</span>
        <div class="crawl-card__tip-list">
          <button type="button" class="chip" @click="applyKeyword('大语言模型安全评测最新进展')">
            大模型安全
          </button>
          <button type="button" class="chip" @click="applyKeyword('Transformer 在医学影像中的应用综述')">
            医学影像
          </button>
        </div>
      </div>

      <div class="actions">
        <button class="btn" type="submit" :disabled="isLoading || !keyword.trim().length">
          <span v-if="isLoading">正在触发…</span>
          <span v-else>开始爬取</span>
        </button>
      </div>
    </form>

    <div v-if="successMessage" class="alert alert--success">{{ successMessage }}</div>
    <section v-if="summary" class="crawl-card__summary">
      <h3>执行摘要</h3>
      <ul>
        <li>
          <strong>候选论文：</strong>
          {{ summary.candidates }} 篇
        </li>
        <li>
          <strong>成功下载：</strong>
          {{ summary.downloaded }} 篇
        </li>
        <li>
          <strong>是否入库：</strong>
          {{ summary.ingest_ran ? '是' : '否' }}
        </li>
        <li v-if="summary.providers?.length">
          <strong>数据源：</strong>
          {{ summary.providers.join('，') }}
        </li>
        <li v-if="summary.queries?.length">
          <strong>检索词：</strong>
          {{ summary.queries.join('，') }}
        </li>
      </ul>
    </section>
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
  submit: [query: string];
}>();

const keyword = ref('');
const isLoading = computed(() => props.isLoading);
const successMessage = computed(() => {
  if (!props.result) {
    return '';
  }
  if (props.result.message) {
    return props.result.message;
  }
  if (props.result.status === 'ok') {
    return '爬取任务已完成';
  }
  return props.result.status;
});
const error = computed(() => props.error);
const summary = computed(() => props.result?.summary ?? null);

watch(
  () => props.result,
  (value) => {
    if (value) {
      keyword.value = '';
    }
  }
);

function submit() {
  const trimmed = keyword.value.trim();
  if (!trimmed || isLoading.value) {
    return;
  }
  emit('submit', trimmed);
}

function applyKeyword(value: string) {
  keyword.value = value;
}
</script>
