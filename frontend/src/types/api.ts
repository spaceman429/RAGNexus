export interface ApiResponse<T> {
  code: number;
  msg: string;
  data: T;
}

export interface CreateKnowledgeBaseRequest {
  name: string;
  description?: string;
}

export interface KnowledgeBaseData {
  kb_id: string;
  name: string;
  tenant_id: string;
  created_at: string;
}

export interface KnowledgeBaseDetailData {
  kb_id: string;
  tenant_id: string;
  name: string;
  description: string | null;
  settings: Record<string, unknown>;
  document_count: number;
  created_at: string;
  updated_at: string;
}

export interface UpdateKnowledgeBaseRequest {
  name?: string;
  description?: string;
  settings?: Record<string, unknown>;
}

export interface DocumentTreeItem {
  document_id: string;
  title: string;
  status: number;
  chunk_count: number;
  error_message?: string | null;
  created_at: string;
}

export interface KnowledgeBaseTreeItem {
  kb_id: string;
  name: string;
  description: string | null;
  created_at: string;
  documents: DocumentTreeItem[];
}

export interface TenantTreeItem {
  tenant_id: string;
  knowledge_bases: KnowledgeBaseTreeItem[];
}

export interface AuthFeatures {
  allowed_profiles: string[];
  hybrid_allowed: boolean;
  rerank_allowed: boolean;
  query_rewrite_allowed: boolean;
}

export interface AuthLimits {
  retrieve_qps: number;
  retrieve_daily: number;
  max_kb: number;
  max_kb_per_retrieve: number;
  max_documents_per_kb: number;
  max_processing_documents: number;
}

export interface AuthUsage {
  kb_count: number;
  retrieve_daily: number;
}

export interface AuthMeData {
  tenant_id: string;
  tenant_name: string;
  key_prefix: string | null;
  key_name: string | null;
  plan: string;
  features: AuthFeatures;
  limits: AuthLimits;
  usage: AuthUsage;
}

export interface UploadDocumentRequest {
  kb_id: string;
  title: string;
  content: string;
}

export interface UploadDocumentData {
  document_id: string;
  kb_id: string;
  status: number;
  chunk_count: number;
}

export interface UploadFileResult {
  fileName: string;
  relativePath: string;
  status: "submitted" | "success" | "failed";
  documentId?: string;
  chunkCount?: number;
  message?: string;
}

export type RetrievalMode = "vector" | "bm25" | "hybrid";

export interface RetrievalOptions {
  mode?: RetrievalMode;
  vector_top_k?: number;
  bm25_top_k?: number;
  rrf_k?: number;
}

export interface RerankOptions {
  enabled?: boolean;
  top_n?: number;
}

export interface QueryOptions {
  enabled?: boolean;
  strategy?: "noop" | "rewrite";
}

export type RetrieveProfile = "speed" | "balanced" | "quality" | "custom";

export interface RetrieveRequest {
  kb_id?: string;
  kb_ids?: string[];
  user_id: string;
  query: string;
  profile: RetrieveProfile;
  top_k?: number;
  retrieval_options?: RetrievalOptions;
  rerank_options?: RerankOptions;
  query_options?: QueryOptions;
}

export interface RetrievedChunkData {
  kb_id: string;
  kb_name?: string | null;
  document_id: string;
  chunk_id: string;
  title: string;
  content: string;
  score: number;
  vector_score: number | null;
  bm25_score: number | null;
  vector_rank: number | null;
  bm25_rank: number | null;
  retrieval_source: string | null;
  rerank_score: number | null;
  metadata?: Record<string, unknown> | null;
}

export interface RetrieveRerankMetadata {
  enabled: boolean;
  provider: string;
  llm_provider: string | null;
  model: string | null;
  top_n: number | null;
  candidate_count: number;
  degraded: boolean;
  error: string | null;
}

export interface RetrieveRetrievalMetadata {
  mode?: string;
  fusion?: string | null;
  rrf_k?: number | null;
  vector_store?: string;
  keyword_search?: string | null;
  vector_top_k?: number | null;
  bm25_top_k?: number | null;
  vector_count?: number;
  bm25_count?: number;
  fused_count?: number;
  degraded?: boolean;
  degraded_reason?: string | null;
  cost_ms?: number;
  multi_kb?: boolean;
  kb_count?: number;
  kb_ids?: string[];
  per_kb_top_k?: number;
}

export interface QueryProcessingMetadata {
  enabled: boolean;
  strategy: string;
  raw_query: string;
  effective_query: string;
  search_query: string;
  latency_ms: number;
  synonym_expansions: string[];
  synonym_applied: boolean;
  degraded: boolean;
  degraded_reason: string | null;
}

export interface TenantPolicyMetadata {
  plan: string;
  retrieve_profile: string;
  effective_mode: string;
  effective_rerank: boolean;
  effective_query_rewrite: boolean;
  max_kb_per_retrieve?: number | null;
  actual_kb_count?: number | null;
}

export interface RetrieveMetadata {
  log_id: string;
  trace_id?: string | null;
  top_k: number;
  vector_store: string;
  latency_ms: number;
  retrieval: RetrieveRetrievalMetadata | null;
  rerank: RetrieveRerankMetadata;
  query_processing: QueryProcessingMetadata | null;
  tenant_policy?: TenantPolicyMetadata | null;
}

export interface RetrieveData {
  query: string;
  kb_id: string;
  kb_ids: string[];
  retrieved_chunks: RetrievedChunkData[];
  metadata: RetrieveMetadata;
}

export interface FeedbackRequest {
  trace_id: string;
  log_id?: string;
  score: number;
  comment?: string;
}

export interface FeedbackData {
  feedback_id: string;
  trace_id: string;
  log_id?: string | null;
  score: number;
}

