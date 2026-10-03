import { useQuery } from '@tanstack/react-query';
import client from '../api/client';
import type { GraphResponse, GraphFilters } from '../types/graph';

interface UseResourceGraphParams {
  filters?: GraphFilters;
  enabled?: boolean;
}

export function useResourceGraph({ filters, enabled = true }: UseResourceGraphParams) {
  return useQuery<GraphResponse>({
    queryKey: ['graph', 'resources', filters],
    queryFn: async () => {
      const params = new URLSearchParams();

      if (filters?.tenant_id) {
        params.append('tenant_id', filters.tenant_id);
      }
      if (filters?.service_type) {
        params.append('service_type', filters.service_type);
      }
      if (filters?.project) {
        params.append('project', filters.project);
      }

      const url = `/graph/resources${params.toString() ? '?' + params.toString() : ''}`;
      const response = await client.get<GraphResponse>(url);
      return response.data;
    },
    enabled,
    staleTime: 60000, // 1 minute - graph data changes less frequently
  });
}
