export interface AskRequest {
  q: string;
  k?: number;
}

export interface AskResponse {
  answer: string;
  references?: (string | ReferenceItem)[];
  elapsed?: number;
}

export interface CrawlRequest {
  query: string;
  providers?: string;
  max_per_source?: number;
  run_ingest?: boolean;
}

export interface CrawlResponse {
  status: string;
  message?: string;
  summary?: CrawlSummary;
}

export interface CrawlSummary {
  candidates: number;
  downloaded: number;
  ingest_ran: boolean;
  ingest_summary?: Record<string, unknown>;
  metadata_written?: boolean;
  providers?: string[];
  queries?: string[];
}

export interface ReferenceItem {
  title?: string;
  source?: string;
  chunk_id?: string | number;
  url?: string;
}

export interface ApiErrorPayload {
  error: string;
  detail?: unknown;
}

export type ApiResult<T> =
  | { ok: true; data: T }
  | { ok: false; status: number; message: string };
