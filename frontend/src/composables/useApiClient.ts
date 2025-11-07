import { computed, reactive } from 'vue';
import type {
  ApiResult,
  AskRequest,
  AskResponse,
  CrawlRequest,
  CrawlResponse
} from '@/types/api';

interface ApiClientOptions {
  baseUrl: string;
  headers?: Record<string, string>;
}

async function request<T>(url: string, options: RequestInit): Promise<ApiResult<T>> {
  try {
    const response = await fetch(url, options);
    if (!response.ok) {
      let message = response.statusText;
      try {
        const data = (await response.json()) as { error?: string; message?: string };
        message = data.error || data.message || message;
      } catch (error) {
        // ignore JSON parsing errors and use default message
      }
      return { ok: false, status: response.status, message };
    }

    const payload = (await response.json()) as T;
    return { ok: true, data: payload };
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Network error';
    return { ok: false, status: 0, message };
  }
}

export function useApiClient(options: ApiClientOptions) {
  const config = reactive({ ...options });

  const baseUrl = computed(() => config.baseUrl.trim().replace(/\/$/, ''));

  return {
    config,
    async ask(payload: AskRequest) {
      return request<AskResponse>(`${baseUrl.value}/ask`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...config.headers
        },
        body: JSON.stringify(payload)
      });
    },
    async crawl(payload: CrawlRequest) {
      return request<CrawlResponse>(`${baseUrl.value}/crawl`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...config.headers
        },
        body: JSON.stringify(payload)
      });
    }
  };
}
