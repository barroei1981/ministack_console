import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import client from '../api/client';
import type {
  FunctionListResponse,
  CreateFunctionRequest,
  LambdaFunction,
  DeleteFunctionResponse,
} from '../types/lambda';

export function useFunctions(tenantId: string | null) {
  return useQuery<FunctionListResponse>({
    queryKey: ['lambda-functions', tenantId],
    queryFn: async () => {
      if (!tenantId) {
        return { functions: [], tenant_id: '', total: 0 };
      }
      const response = await client.get<FunctionListResponse>(
        '/resources/lambda/functions',
        { params: { tenant_id: tenantId } }
      );
      return response.data;
    },
    enabled: !!tenantId,
  });
}

export function useFunction(name: string | null, tenantId: string | null) {
  return useQuery<LambdaFunction>({
    queryKey: ['lambda-function', name, tenantId],
    queryFn: async () => {
      if (!name || !tenantId) {
        throw new Error('Function name and tenant ID required');
      }
      const response = await client.get<LambdaFunction>(
        `/resources/lambda/functions/${name}`,
        { params: { tenant_id: tenantId } }
      );
      return response.data;
    },
    enabled: !!name && !!tenantId,
  });
}

export function useCreateFunction() {
  const queryClient = useQueryClient();

  return useMutation<LambdaFunction, Error, CreateFunctionRequest>({
    mutationFn: async (data: CreateFunctionRequest) => {
      const response = await client.post<LambdaFunction>(
        '/resources/lambda/functions',
        data
      );
      return response.data;
    },
    onSuccess: (_, variables) => {
      toast.success('Function created successfully');
      queryClient.invalidateQueries({
        queryKey: ['lambda-functions', variables.tenant_id],
      });
    },
    onError: (error) => {
      if (error instanceof Error) {
        if ('response' in error && typeof error.response === 'object' && error.response !== null) {
          const axiosError = error as {
            response: { status: number; data: { detail: string } };
          };
          if (axiosError.response.status === 400) {
            toast.error(`Invalid configuration: ${axiosError.response.data.detail}`);
          } else if (axiosError.response.status === 409) {
            toast.error('Function already exists');
          } else {
            toast.error('Failed to create function');
          }
        } else {
          toast.error('Failed to create function');
        }
      } else {
        toast.error('Failed to create function');
      }
    },
  });
}

export function useDeleteFunction() {
  const queryClient = useQueryClient();

  return useMutation<
    DeleteFunctionResponse,
    Error,
    { name: string; tenant_id: string }
  >({
    mutationFn: async ({ name, tenant_id }) => {
      const response = await client.delete<DeleteFunctionResponse>(
        `/resources/lambda/functions/${name}`,
        { params: { tenant_id } }
      );
      return response.data;
    },
    onSuccess: (_, variables) => {
      toast.success('Function deleted successfully');
      queryClient.invalidateQueries({
        queryKey: ['lambda-functions', variables.tenant_id],
      });
    },
    onError: () => {
      toast.error('Failed to delete function');
    },
  });
}
