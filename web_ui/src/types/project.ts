export interface ProjectSummary {
  name: string;
  resource_count: number;
  tenant_id: string;
  description?: string;
  created_at?: string;
}

export interface ProjectListResponse {
  projects: ProjectSummary[];
  tenant_id: string;
}

export interface CreateProjectRequest {
  name: string;
  description?: string;
  tenant_id: string;
}

export interface ProjectDetail {
  name: string;
  description?: string;
  tenant_id: string;
  created_at?: string;
  resource_count: number;
  resource_counts_by_service: Record<string, number>;
}

export interface BulkDeleteResponse {
  deleted_count: number;
  project_name: string;
  tenant_id: string;
}
