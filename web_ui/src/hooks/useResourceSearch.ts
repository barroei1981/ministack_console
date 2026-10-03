import { useQuery } from '@tanstack/react-query';
import client from '../api/client';
import type { SearchResponse, SearchFilters } from '../types/search';

interface UseResourceSearchParams {
  query: string;
  filters?: SearchFilters;
  enabled?: boolean;
}

export function useResourceSearch({ query, filters, enabled = true }: UseResourceSearchParams) {
  return useQuery<SearchResponse>({
    queryKey: ['search', 'resources', query, filters],
    queryFn: async () => {
      if (!query || query.trim().length === 0) {
        return { results: [], count: 0, query: '' };
      }

      const params = new URLSearchParams({ q: query.trim() });

      if (filters?.tenant_id) {
        params.append('tenant_id', filters.tenant_id);
      }
      if (filters?.service_type) {
        params.append('service_type', filters.service_type);
      }
      if (filters?.project) {
        params.append('project', filters.project);
      }

      const response = await client.get<SearchResponse>(`/search/resources?${params.toString()}`);
      return response.data;
    },
    enabled: enabled && query.trim().length > 0,
  });
}
