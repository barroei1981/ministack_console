import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import client from '../api/client';
import type {
  BucketListResponse,
  CreateBucketRequest,
  Bucket,
  DeleteBucketResponse
} from '../types/s3';

export function useBuckets(tenantId: string | null) {
  return useQuery<BucketListResponse>({
    queryKey: ['buckets', tenantId],
    queryFn: async () => {
      if (!tenantId) {
        return { buckets: [], tenant_id: '', total: 0 };
      }
      const response = await client.get<BucketListResponse>('/resources/s3/buckets');
      return response.data;
    },
    enabled: !!tenantId,
  });
}

export function useCreateBucket() {
  const queryClient = useQueryClient();

  return useMutation<Bucket, Error, CreateBucketRequest>({
    mutationFn: async (data: CreateBucketRequest) => {
      const response = await client.post<Bucket>('/resources/s3/buckets', data);
      return response.data;
    },
    onSuccess: (_, variables) => {
      toast.success('Bucket created successfully');
      queryClient.invalidateQueries({ queryKey: ['buckets', variables.tenant_id] });
    },
    onError: (error) => {
      if (error instanceof Error) {
        if ('response' in error && typeof error.response === 'object' && error.response !== null) {
          const axiosError = error as { response: { status: number; data: { detail: string } } };
          if (axiosError.response.status === 400) {
            toast.error(`Invalid bucket name: ${axiosError.response.data.detail}`);
          } else if (axiosError.response.status === 409) {
            toast.error('Bucket already exists');
          } else {
            toast.error('Failed to create bucket');
          }
        } else {
          toast.error('Failed to create bucket');
        }
      }
    },
  });
}

export function useBucket(name: string | undefined, tenantId: string | null) {
  return useQuery<Bucket>({
    queryKey: ['bucket', name, tenantId],
    queryFn: async () => {
      if (!name || !tenantId) {
        throw new Error('Bucket name and tenant ID are required');
      }
      const response = await client.get<Bucket>(`/resources/s3/buckets/${name}`);
      return response.data;
    },
    enabled: !!name && !!tenantId,
  });
}

export function useUpdateVersioning() {
  const queryClient = useQueryClient();

  return useMutation<
    Bucket,
    Error,
    { bucketName: string; enabled: boolean; tenantId: string },
    { previous: Bucket | undefined }
  >({
    mutationFn: async ({ bucketName, enabled, tenantId }) => {
      const response = await client.put<Bucket>(
        `/resources/s3/buckets/${bucketName}/versioning`,
        {
          enabled,
          tenant_id: tenantId,
        }
      );
      return response.data;
    },
    onMutate: async ({ bucketName, enabled, tenantId }) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: ['bucket', bucketName, tenantId] });

      // Snapshot current value
      const previous = queryClient.getQueryData<Bucket>(['bucket', bucketName, tenantId]);

      // Optimistically update
      queryClient.setQueryData(['bucket', bucketName, tenantId], (old: any) => ({
        ...old,
        versioning: enabled ? 'Enabled' : 'Suspended',
        state: { ...old.state, versioning: enabled ? 'Enabled' : 'Suspended' },
      }));

      return { previous };
    },
    onError: (_error, variables, context) => {
      // Revert on error
      if (context?.previous) {
        queryClient.setQueryData(
          ['bucket', variables.bucketName, variables.tenantId],
          context.previous
        );
      }
      toast.error('Failed to update versioning');
    },
    onSuccess: () => {
      toast.success('Versioning updated');
    },
  });
}

export function useDeleteBucket() {
  const queryClient = useQueryClient();

  return useMutation<
    DeleteBucketResponse,
    Error,
    { bucketName: string; tenantId: string; force?: boolean }
  >({
    mutationFn: async ({ bucketName, force = false }) => {
      const params = force ? `?force=true` : '';
      const response = await client.delete<DeleteBucketResponse>(
        `/resources/s3/buckets/${bucketName}${params}`
      );
      return response.data;
    },
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['buckets', variables.tenantId] });
      if (data.objects_deleted > 0) {
        toast.success(`Bucket and ${data.objects_deleted} objects deleted`);
      } else {
        toast.success('Bucket deleted');
      }
    },
    onError: (error) => {
      if (error instanceof Error) {
        if ('response' in error && typeof error.response === 'object' && error.response !== null) {
          const axiosError = error as { response: { status: number; data: { detail: string } } };
          if (axiosError.response.status === 404) {
            toast.error('Bucket not found');
          } else {
            toast.error('Delete failed');
          }
        } else {
          toast.error('Delete failed');
        }
      }
    },
  });
}
