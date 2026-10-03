import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import client from '../api/client';
import type { BucketListResponse, CreateBucketRequest, Bucket } from '../types/s3';

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
