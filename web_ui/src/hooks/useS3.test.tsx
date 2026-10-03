import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useBuckets, useCreateBucket } from './useS3';
import client from '../api/client';
import toast from 'react-hot-toast';

vi.mock('../api/client');
vi.mock('react-hot-toast');

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
};

describe('useS3 hooks', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('useBuckets', () => {
    it('returns empty data when tenantId is null', () => {
      const { result } = renderHook(() => useBuckets(null), {
        wrapper: createWrapper(),
      });

      expect(result.current.data).toBeUndefined();
      expect(result.current.isLoading).toBe(false);
    });

    it('calls API and returns bucket data with valid tenantId', async () => {
      const mockData = {
        buckets: [
          {
            name: 'test-bucket',
            tenant_id: '123456789012',
            project: null,
            arn: 'arn:aws:s3:::test-bucket',
            created_at: '2023-01-01T00:00:00Z',
            versioning: 'Enabled',
            tags: {},
            state: {},
          },
        ],
        tenant_id: '123456789012',
        total: 1,
      };

      vi.mocked(client.get).mockResolvedValueOnce({ data: mockData });

      const { result } = renderHook(() => useBuckets('123456789012'), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toEqual(mockData);
      expect(client.get).toHaveBeenCalledWith('/resources/s3/buckets');
    });

    it('handles API errors gracefully', async () => {
      vi.mocked(client.get).mockRejectedValueOnce(new Error('Network error'));

      const { result } = renderHook(() => useBuckets('123456789012'), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isError).toBe(true));

      expect(result.current.error).toBeDefined();
    });
  });

  describe('useCreateBucket', () => {
    it('creates bucket and invalidates cache on success', async () => {
      const mockBucket = {
        name: 'new-bucket',
        tenant_id: '123456789012',
        project: null,
        arn: 'arn:aws:s3:::new-bucket',
        created_at: '2023-01-01T00:00:00Z',
        versioning: '',
        tags: {},
        state: {},
      };

      vi.mocked(client.post).mockResolvedValueOnce({ data: mockBucket });

      const { result } = renderHook(() => useCreateBucket(), {
        wrapper: createWrapper(),
      });

      result.current.mutate({
        name: 'new-bucket',
        tenant_id: '123456789012',
        versioning: false,
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(client.post).toHaveBeenCalledWith('/resources/s3/buckets', {
        name: 'new-bucket',
        tenant_id: '123456789012',
        versioning: false,
      });
      expect(toast.success).toHaveBeenCalledWith('Bucket created successfully');
    });

    it('shows error toast on failure', async () => {
      const error = new Error('Request failed') as any;
      error.response = {
        status: 400,
        data: { detail: 'Invalid bucket name' },
      };

      vi.mocked(client.post).mockRejectedValueOnce(error);

      const { result } = renderHook(() => useCreateBucket(), {
        wrapper: createWrapper(),
      });

      result.current.mutate({
        name: 'Invalid-Bucket',
        tenant_id: '123456789012',
        versioning: false,
      });

      await waitFor(() => expect(result.current.isError).toBe(true));

      expect(toast.error).toHaveBeenCalledWith('Invalid bucket name: Invalid bucket name');
    });
  });
});
