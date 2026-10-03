import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BucketList } from './BucketList';
import * as useS3 from '../../../hooks/useS3';

vi.mock('../../../hooks/useS3');
vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
};

describe('BucketList', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    delete (window as { location?: unknown }).location;
    (window as { location: { search: string } }).location = {
      search: '?tenant_id=123456789012',
    };
    // Mock useCreateBucket for BucketCreate modal
    vi.mocked(useS3.useCreateBucket).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
      isError: false,
      isSuccess: false,
      error: null,
      mutate: vi.fn(),
      reset: vi.fn(),
    } as any);
  });

  it('renders with tenant_id and shows bucket list', async () => {
    const mockBuckets = [
      {
        name: 'test-bucket-1',
        tenant_id: '123456789012',
        project: null,
        arn: 'arn:aws:s3:::test-bucket-1',
        created_at: '2023-01-01T00:00:00Z',
        versioning: 'Enabled',
        tags: {},
        state: {},
      },
      {
        name: 'test-bucket-2',
        tenant_id: '123456789012',
        project: null,
        arn: 'arn:aws:s3:::test-bucket-2',
        created_at: '2023-01-02T00:00:00Z',
        versioning: '',
        tags: { env: 'prod' },
        state: {},
      },
    ];

    vi.mocked(useS3.useBuckets).mockReturnValue({
      data: { buckets: mockBuckets, tenant_id: '123456789012', total: 2 },
      isLoading: false,
      error: null,
      isError: false,
      isSuccess: true,
    } as any);

    render(<BucketList />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('test-bucket-1')).toBeInTheDocument();
      expect(screen.getByText('test-bucket-2')).toBeInTheDocument();
    });
  });

  it('renders without tenant_id and shows warning', () => {
    (window as { location: { search: string } }).location.search = '';

    vi.mocked(useS3.useBuckets).mockReturnValue({
      data: undefined,
      isLoading: false,
      error: null,
      isError: false,
      isSuccess: false,
    } as any);

    render(<BucketList />, { wrapper: createWrapper() });

    expect(screen.getByText('s3.errors.missingTenantId')).toBeInTheDocument();
  });

  it('filters buckets by search query (case-insensitive)', async () => {
    const user = userEvent.setup();
    const mockBuckets = [
      {
        name: 'prod-bucket',
        tenant_id: '123456789012',
        project: null,
        arn: 'arn:aws:s3:::prod-bucket',
        created_at: '2023-01-01T00:00:00Z',
        versioning: '',
        tags: {},
        state: {},
      },
      {
        name: 'test-bucket',
        tenant_id: '123456789012',
        project: null,
        arn: 'arn:aws:s3:::test-bucket',
        created_at: '2023-01-02T00:00:00Z',
        versioning: '',
        tags: {},
        state: {},
      },
    ];

    vi.mocked(useS3.useBuckets).mockReturnValue({
      data: { buckets: mockBuckets, tenant_id: '123456789012', total: 2 },
      isLoading: false,
      error: null,
      isError: false,
      isSuccess: true,
    } as any);

    render(<BucketList />, { wrapper: createWrapper() });

    const searchInput = screen.getByPlaceholderText('common.search');
    await user.type(searchInput, 'TEST');

    await waitFor(() => {
      expect(screen.getByText('test-bucket')).toBeInTheDocument();
      expect(screen.queryByText('prod-bucket')).not.toBeInTheDocument();
    });
  });

  it('shows empty state when no buckets', () => {
    vi.mocked(useS3.useBuckets).mockReturnValue({
      data: { buckets: [], tenant_id: '123456789012', total: 0 },
      isLoading: false,
      error: null,
      isError: false,
      isSuccess: true,
    } as any);

    render(<BucketList />, { wrapper: createWrapper() });

    expect(screen.getByText('s3.empty')).toBeInTheDocument();
  });

  it('shows error state on API failure', () => {
    vi.mocked(useS3.useBuckets).mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error('API error'),
      isError: true,
      isSuccess: false,
    } as any);

    render(<BucketList />, { wrapper: createWrapper() });

    expect(screen.getByText('API error')).toBeInTheDocument();
  });

  it('shows loading state', () => {
    vi.mocked(useS3.useBuckets).mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
      isError: false,
      isSuccess: false,
    } as any);

    render(<BucketList />, { wrapper: createWrapper() });

    const spinner = document.querySelector('.animate-spin');
    expect(spinner).toBeInTheDocument();
  });
});
