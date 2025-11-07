export interface AskRequest {
  query: string;
}

export interface AskResponse {
  answer: string;
  references?: string[];
  elapsed?: number;
}

export interface CrawlRequest {
  seedUrl: string;
}

export interface CrawlResponse {
  status: string;
  message?: string;
}

export interface ApiErrorPayload {
  error: string;
  detail?: unknown;
}

export type ApiResult<T> =
  | { ok: true; data: T }
  | { ok: false; status: number; message: string };
