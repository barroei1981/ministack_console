export interface SearchResource {
  id: string;
  name: string;
  type: string;
  tenant_id: string;
  project?: string;
  created_at?: string;
  [key: string]: unknown;
}

export interface SearchResponse {
  results: SearchResource[];
  count: number;
  query: string;
}

export interface SearchFilters {
  tenant_id?: string;
  service_type?: string;
  project?: string;
}
