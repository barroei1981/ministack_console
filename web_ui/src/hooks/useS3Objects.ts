import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import client from '../api/client';
import type {
  S3ObjectListResponse,
  UploadObjectRequest,
  DeleteObjectsRequest,
} from '../types/s3';

export function useS3Objects(
  bucketName: string | null,
  tenantId: string | null,
  prefix: string = ''
) {
  return useQuery<S3ObjectListResponse>({
    queryKey: ['s3-objects', bucketName, tenantId, prefix],
    queryFn: async () => {
      if (!bucketName || !tenantId) {
        return { objects: [], folders: [], is_truncated: false, prefix: '' };
      }
      const response = await client.get<S3ObjectListResponse>(
        `/resources/s3/buckets/${bucketName}/objects`,
        { params: { tenant_id: tenantId, prefix } }
      );
      return response.data;
    },
    enabled: !!bucketName && !!tenantId,
  });
}

export function useUploadObject(bucketName: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: UploadObjectRequest) => {
      const formData = new FormData();
      formData.append('key', data.key);
      formData.append('file', data.file);
      if (data.metadata) {
        formData.append('metadata', JSON.stringify(data.metadata));
      }

      const response = await client.post(
        `/resources/s3/buckets/${bucketName}/objects`,
        formData,
        {
          params: { tenant_id: data.tenant_id },
          headers: { 'Content-Type': 'multipart/form-data' },
          onUploadProgress: data.onProgress,
        }
      );
      return response.data;
    },
    onSuccess: (_, variables) => {
      toast.success('File uploaded successfully');
      // Invalidate object list for current prefix
      const currentPrefix = variables.key.substring(
        0,
        variables.key.lastIndexOf('/') + 1
      );
      queryClient.invalidateQueries({
        queryKey: ['s3-objects', bucketName, variables.tenant_id, currentPrefix],
      });
    },
    onError: () => {
      toast.error('Failed to upload file');
    },
  });
}

export function useDownloadObject(bucketName: string) {
  return useMutation({
    mutationFn: async ({
      key,
      tenant_id,
    }: {
      key: string;
      tenant_id: string;
    }) => {
      const response = await client.get<{ download_url: string }>(
        `/resources/s3/buckets/${bucketName}/objects/${key}/download`,
        { params: { tenant_id } }
      );
      return response.data.download_url;
    },
    onSuccess: (url) => {
      window.open(url, '_blank');
    },
    onError: () => {
      toast.error('Failed to download file');
    },
  });
}

export function useDeleteObjects(bucketName: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: DeleteObjectsRequest) => {
      const response = await client.delete(
        `/resources/s3/buckets/${bucketName}/objects`,
        {
          params: {
            tenant_id: data.tenant_id,
            keys: data.keys,
          },
        }
      );
      return response.data;
    },
    onSuccess: (_, variables) => {
      toast.success(`Deleted ${variables.keys.length} object(s)`);
      // Invalidate all object list queries for this bucket
      queryClient.invalidateQueries({
        queryKey: ['s3-objects', bucketName, variables.tenant_id],
      });
    },
    onError: () => {
      toast.error('Failed to delete objects');
    },
  });
}
