<template>
  <div class="layout">
    <ApiSettingsForm v-model="settings" @submit="handleSettingsUpdate" />

    <div class="layout__grid">
      <AskForm
        :is-loading="askState.isLoading"
        :answer="askState.answer"
        :error="askState.error"
        @submit="handleAsk"
      />

      <CrawlTrigger
        :is-loading="crawlState.isLoading"
        :result="crawlState.result"
        :error="crawlState.error"
        @submit="handleCrawl"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, watch } from 'vue';
import ApiSettingsForm from '@/components/ApiSettingsForm.vue';
import AskForm from '@/components/AskForm.vue';
import CrawlTrigger from '@/components/CrawlTrigger.vue';
import { usePersistentState } from '@/composables/usePersistentState';
import { useApiClient } from '@/composables/useApiClient';
import type { AskResponse, CrawlResponse } from '@/types/api';
import type { ApiSettings } from '@/types/settings';

const settings = usePersistentState<ApiSettings>('rag-console-settings', {
  baseUrl: 'http://localhost:8000',
  apiKey: ''
});

const apiClient = useApiClient({ baseUrl: settings.value.baseUrl });

watch(
  settings,
  (value) => {
    apiClient.config.baseUrl = value.baseUrl;
    const headers: Record<string, string> = {};
    if (value.apiKey) {
      headers.Authorization = `Bearer ${value.apiKey}`;
    }
    apiClient.config.headers = Object.keys(headers).length ? headers : undefined;
  },
  { immediate: true, deep: true }
);

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

function handleSettingsUpdate(newSettings: ApiSettings) {
  settings.value = {
    baseUrl: newSettings.baseUrl.trim(),
    apiKey: newSettings.apiKey?.trim() || ''
  };
}

async function handleAsk(query: string) {
  if (!settings.value.baseUrl.trim()) {
    askState.error = 'Please configure the backend base URL before asking questions.';
    askState.answer = null;
    return;
  }

  askState.isLoading = true;
  askState.error = null;
  askState.answer = null;

  const response = await apiClient.ask({ query });
  askState.isLoading = false;

  if (response.ok) {
    askState.answer = response.data;
  } else {
    askState.error = `Failed to fetch answer (${response.status || 'network'}): ${response.message}`;
  }
}

async function handleCrawl(seedUrl: string) {
  if (!settings.value.baseUrl.trim()) {
    crawlState.error = 'Please configure the backend base URL before triggering crawls.';
    crawlState.result = null;
    return;
  }

  crawlState.isLoading = true;
  crawlState.error = null;
  crawlState.result = null;

  const response = await apiClient.crawl({ seedUrl });
  crawlState.isLoading = false;

  if (response.ok) {
    crawlState.result = response.data;
  } else {
    crawlState.error = `Failed to trigger crawl (${response.status || 'network'}): ${response.message}`;
  }
}
</script>
