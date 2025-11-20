export interface AskRequest {
  q: string;
  k?: number;
}

export interface AskResponse {
  answer: string;
  references?: (string | ReferenceItem)[];
  elapsed?: number;
  cues?: string[];
  graph?: GraphNode[];
  reason?: string;
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

export interface GraphEdge {
  target: string;
  type: string;
}

export interface GraphNode {
  label: string;
  type?: string;
  score?: number;
  summary?: string;
  edges?: GraphEdge[];
}

export interface ApiErrorPayload {
  error: string;
  detail?: unknown;
}

export type ApiResult<T> =
  | { ok: true; data: T }
  | { ok: false; status: number; message: string };
