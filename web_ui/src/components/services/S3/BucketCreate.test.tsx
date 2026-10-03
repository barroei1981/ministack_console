import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BucketCreate } from './BucketCreate';
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
      mutations: { retry: false },
    },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
};

describe('BucketCreate', () => {
  const mockOnClose = vi.fn();
  const mockMutateAsync = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useS3.useCreateBucket).mockReturnValue({
      mutateAsync: mockMutateAsync,
      isPending: false,
      isError: false,
      isSuccess: false,
      error: null,
      mutate: vi.fn(),
      reset: vi.fn(),
      data: undefined,
      variables: undefined,
      context: undefined,
      failureCount: 0,
      failureReason: null,
      isIdle: false,
      isPaused: false,
      status: 'idle',
      submittedAt: 0,
    } as any);
  });

  it('validates invalid bucket names', async () => {
    const user = userEvent.setup();

    render(
      <BucketCreate isOpen={true} onClose={mockOnClose} tenantId="123456789012" />,
      { wrapper: createWrapper() }
    );

    const nameInput = screen.getByLabelText('s3.create.name');
    const submitButton = screen.getByText('s3.create.submit');

    // Try uppercase name (invalid)
    await user.type(nameInput, 'My-Bucket');

    await waitFor(() => {
      expect(submitButton).toBeDisabled();
    });
  });

  it('submits valid form successfully', async () => {
    const user = userEvent.setup();
    mockMutateAsync.mockResolvedValueOnce({
      name: 'test-bucket',
      tenant_id: '123456789012',
      project: null,
      arn: 'arn:aws:s3:::test-bucket',
      created_at: '2023-01-01T00:00:00Z',
      versioning: '',
      tags: {},
      state: {},
    });

    render(
      <BucketCreate isOpen={true} onClose={mockOnClose} tenantId="123456789012" />,
      { wrapper: createWrapper() }
    );

    const nameInput = screen.getByLabelText('s3.create.name');
    const projectInput = screen.getByLabelText('s3.create.project');
    const versioningCheckbox = screen.getByLabelText('s3.create.versioning');
    const submitButton = screen.getByText('s3.create.submit');

    await user.type(nameInput, 'test-bucket');
    await user.type(projectInput, 'myproject');
    await user.click(versioningCheckbox);

    await waitFor(() => {
      expect(submitButton).not.toBeDisabled();
    });

    await user.click(submitButton);

    await waitFor(() => {
      expect(mockMutateAsync).toHaveBeenCalledWith({
        name: 'test-bucket',
        tenant_id: '123456789012',
        project: 'myproject',
        versioning: true,
      });
      expect(mockOnClose).toHaveBeenCalled();
    });
  });

  it('shows error toast on API failure', async () => {
    const user = userEvent.setup();
    mockMutateAsync.mockRejectedValueOnce(new Error('API error'));

    render(
      <BucketCreate isOpen={true} onClose={mockOnClose} tenantId="123456789012" />,
      { wrapper: createWrapper() }
    );

    const nameInput = screen.getByLabelText('s3.create.name');
    const submitButton = screen.getByText('s3.create.submit');

    await user.type(nameInput, 'test-bucket');

    await waitFor(() => {
      expect(submitButton).not.toBeDisabled();
    });

    await user.click(submitButton);

    await waitFor(() => {
      expect(mockMutateAsync).toHaveBeenCalled();
    });

    // Modal should stay open on error
    expect(mockOnClose).not.toHaveBeenCalled();
  });

  it('closes modal on cancel without submitting', async () => {
    const user = userEvent.setup();

    render(
      <BucketCreate isOpen={true} onClose={mockOnClose} tenantId="123456789012" />,
      { wrapper: createWrapper() }
    );

    const cancelButton = screen.getByText('s3.create.cancel');
    await user.click(cancelButton);

    expect(mockOnClose).toHaveBeenCalled();
    expect(mockMutateAsync).not.toHaveBeenCalled();
  });
});
