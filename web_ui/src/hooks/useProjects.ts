import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import client from '../api/client';
import type {
  ProjectListResponse,
  CreateProjectRequest,
  ProjectDetail,
  BulkDeleteResponse,
} from '../types/project';

export function useProjects(tenantId: string | null) {
  return useQuery<ProjectListResponse>({
    queryKey: ['projects', tenantId],
    queryFn: async () => {
      if (!tenantId) {
        return { projects: [], tenant_id: '' };
      }
      const response = await client.get<ProjectListResponse>(`/tenants/${tenantId}/projects`);
      return response.data;
    },
    enabled: !!tenantId,
  });
}

export function useCreateProject() {
  const queryClient = useQueryClient();

  return useMutation<ProjectDetail, Error, CreateProjectRequest>({
    mutationFn: async (data: CreateProjectRequest) => {
      const response = await client.post<ProjectDetail>('/projects', data);
      return response.data;
    },
    onSuccess: (_, variables) => {
      toast.success('Project created successfully');
      queryClient.invalidateQueries({ queryKey: ['projects', variables.tenant_id] });
    },
    onError: (error) => {
      if (error instanceof Error) {
        if ('response' in error && typeof error.response === 'object' && error.response !== null) {
          const axiosError = error as { response: { status: number; data: { detail: string } } };
          if (axiosError.response.status === 409) {
            toast.error('Project already exists');
          } else {
            toast.error('Failed to create project');
          }
        } else {
          toast.error('Failed to create project');
        }
      }
    },
  });
}

export function useProjectDetail(projectName: string, tenantId: string | null) {
  return useQuery<ProjectDetail>({
    queryKey: ['project', projectName, tenantId],
    queryFn: async () => {
      if (!tenantId) {
        throw new Error('Tenant ID required');
      }
      const response = await client.get<ProjectDetail>(`/projects/${projectName}?tenant_id=${tenantId}`);
      return response.data;
    },
    enabled: !!projectName && !!tenantId,
  });
}

export function useBulkDeleteResources() {
  const queryClient = useQueryClient();

  return useMutation<BulkDeleteResponse, Error, { projectName: string; tenantId: string }>({
    mutationFn: async ({ projectName, tenantId }) => {
      const response = await client.delete<BulkDeleteResponse>(
        `/projects/${projectName}/resources?tenant_id=${tenantId}`
      );
      return response.data;
    },
    onSuccess: (data, variables) => {
      toast.success(`Deleted ${data.deleted_count} resources from project`);
      queryClient.invalidateQueries({ queryKey: ['project', variables.projectName, variables.tenantId] });
      queryClient.invalidateQueries({ queryKey: ['projects', variables.tenantId] });
    },
    onError: () => {
      toast.error('Failed to delete resources');
    },
  });
}
