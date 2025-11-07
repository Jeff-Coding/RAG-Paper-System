import type {
  ApiResult,
  AskRequest,
  AskResponse,
  CrawlRequest,
  CrawlResponse
} from '@/types/api';

const API_BASE_URL = 'http://127.0.0.1:8000';

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

export function useApiClient() {
  return {
    async ask(payload: AskRequest) {
      return request<AskResponse>(`${API_BASE_URL}/ask`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
      });
    },
    async crawl(payload: CrawlRequest) {
      return request<CrawlResponse>(`${API_BASE_URL}/crawl`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
      });
    }
  };
}
