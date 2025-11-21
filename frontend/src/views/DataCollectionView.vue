<template>
  <div class="collect-page">
    <header class="page-header">
      <div>
        <p class="card__eyebrow">数据收集</p>
        <h2>集中启动爬虫，批量获取论文数据</h2>
        <p>输入关键词即可抓取多源文献，随后再回到主页面发起问答。</p>
      </div>

      <RouterLink class="btn btn--ghost" to="/">返回问答</RouterLink>
    </header>

    <section class="card collect-card">
      <p class="card__eyebrow">爬虫任务</p>
      <h3>触发数据收集</h3>
      <p class="collect-card__hint">默认会从 arXiv、OpenAlex、Semantic Scholar 抓取并入库。</p>

      <CrawlTrigger
        :is-loading="crawlState.isLoading"
        :result="crawlState.result"
        :error="crawlState.error"
        @submit="handleCrawl"
      />
    </section>
  </div>
</template>

<script setup lang="ts">
import { reactive } from 'vue';
import CrawlTrigger from '@/components/CrawlTrigger.vue';
import { useApiClient } from '@/composables/useApiClient';
import type { CrawlResponse } from '@/types/api';

const apiClient = useApiClient();
const DEFAULT_MAX_PER_SOURCE = 3;

const crawlState = reactive({
  isLoading: false,
  result: null as CrawlResponse | null,
  error: null as string | null
});

async function handleCrawl(query: string) {
  crawlState.isLoading = true;
  crawlState.error = null;
  crawlState.result = null;

  const response = await apiClient.crawl({
    query,
    max_per_source: DEFAULT_MAX_PER_SOURCE
  });

  crawlState.isLoading = false;

  if ('status' in response) {
    crawlState.error = `触发失败（${response.status || '网络'}）：${response.message}`;
    return;
  }

  crawlState.result = response.data;
}
</script>
