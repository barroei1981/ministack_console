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

export interface S3Object {
  key: string;
  size: number;
  last_modified: string;
  storage_class: string;
  etag: string;
}

export interface S3Folder {
  key: string;
}

export interface S3ObjectListResponse {
  objects: S3Object[];
  folders: S3Folder[];
  is_truncated: boolean;
  next_token?: string;
  prefix: string;
}

export interface UploadObjectRequest {
  key: string;
  file: File;
  tenant_id: string;
  metadata?: Record<string, string>;
  onProgress?: (progressEvent: any) => void;
}

export interface DeleteObjectsRequest {
  keys: string[];
  tenant_id: string;
}
