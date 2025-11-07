<template>
  <div class="dashboard">
    <section class="dashboard__intro card">
      <div class="dashboard__intro-body">
        <h2>论文检索工作台</h2>
        <p>
          使用查询快速定位重点论文，或通过爬取功能批量收集最新资料。
          两个核心动作一目了然，助力高效科研。
        </p>
        <ul class="dashboard__intro-highlights">
          <li>
            <strong>精准问答：</strong>
            输入问题即可获得结构化回复与参考链接。
          </li>
          <li>
            <strong>一键爬取：</strong>
            输入主题关键词，系统自动抓取并入库最新论文。
          </li>
        </ul>
      </div>
    </section>

    <div class="dashboard__grid">
      <AskForm
        class="dashboard__card"
        :is-loading="askState.isLoading"
        :answer="askState.answer"
        :error="askState.error"
        @submit="handleAsk"
      />

      <CrawlTrigger
        class="dashboard__card"
        :is-loading="crawlState.isLoading"
        :result="crawlState.result"
        :error="crawlState.error"
        @submit="handleCrawl"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive } from 'vue';
import AskForm from '@/components/AskForm.vue';
import CrawlTrigger from '@/components/CrawlTrigger.vue';
import { useApiClient } from '@/composables/useApiClient';
import type { AskResponse, CrawlResponse } from '@/types/api';

const apiClient = useApiClient();
const ASK_TOP_K = 10;
const DEFAULT_PROVIDERS = 'arxiv,openalex,semanticscholar';
const DEFAULT_MAX_PER_SOURCE = 1;

const askState = reactive({
  isLoading: false,
  answer: null as AskResponse | null,
  error: null as string | null
});

const crawlState = reactive({
  isLoading: false,
  result: null as CrawlResponse | null,
  error: null as string | null
});

async function handleAsk(query: string) {
  askState.isLoading = true;
  askState.error = null;
  askState.answer = null;

  const response = await apiClient.ask({ q: query, k: ASK_TOP_K });
  askState.isLoading = false;

  if ('status' in response) {
    askState.error = `请求失败（${response.status || '网络'}）：${response.message}`;
    return;
  }

  askState.answer = response.data;
}

async function handleCrawl(query: string) {
  crawlState.isLoading = true;
  crawlState.error = null;
  crawlState.result = null;

  const response = await apiClient.crawl({
    query,
    providers: DEFAULT_PROVIDERS,
    max_per_source: DEFAULT_MAX_PER_SOURCE,
    run_ingest: true
  });
  crawlState.isLoading = false;

  if ('status' in response) {
    crawlState.error = `触发失败（${response.status || '网络'}）：${response.message}`;
    return;
  }

  crawlState.result = response.data;
}
</script>
