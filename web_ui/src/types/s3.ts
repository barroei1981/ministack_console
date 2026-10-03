export interface Bucket {
  name: string;
  tenant_id: string;
  project: string | null;
  arn: string;
  created_at: string;
  versioning: string;
  tags: Record<string, string>;
  state: Record<string, unknown>;
}

export interface CreateBucketRequest {
  name: string;
  tenant_id: string;
  project?: string;
  versioning: boolean;
  tags?: Record<string, string>;
}

export interface BucketListResponse {
  buckets: Bucket[];
  tenant_id: string;
  total: number;
}

export interface UpdateVersioningRequest {
  enabled: boolean;
  tenant_id: string;
}

export interface DeleteBucketResponse {
  deleted: string;
  objects_deleted: number;
}
