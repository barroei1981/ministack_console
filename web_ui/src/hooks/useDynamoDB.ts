import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type {
  CreateTableRequest,
  ScanItemsResponse,
  TableListResponse,
} from '../types/dynamodb';

const API_BASE = 'http://localhost:8000/api';

export function useTables(tenantId: string | null) {
  return useQuery<TableListResponse>({
    queryKey: ['dynamodb', 'tables', tenantId],
    queryFn: async () => {
      if (!tenantId) throw new Error('Tenant ID required');

      const response = await fetch(
        `${API_BASE}/resources/dynamodb/tables?tenant_id=${tenantId}`,
        {
          headers: { 'X-Tenant-ID': tenantId },
        }
      );

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to fetch tables');
      }

      return response.json();
    },
    enabled: !!tenantId,
  });
}

export function useCreateTable() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (request: CreateTableRequest) => {
      const response = await fetch(`${API_BASE}/resources/dynamodb/tables`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Tenant-ID': request.tenant_id,
        },
        body: JSON.stringify(request),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to create table');
      }

      return response.json();
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: ['dynamodb', 'tables', variables.tenant_id],
      });
    },
  });
}

export function useDeleteTable() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      tableName,
      tenantId,
    }: {
      tableName: string;
      tenantId: string;
    }) => {
      const response = await fetch(
        `${API_BASE}/resources/dynamodb/tables/${tableName}?tenant_id=${tenantId}`,
        {
          method: 'DELETE',
          headers: { 'X-Tenant-ID': tenantId },
        }
      );

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to delete table');
      }

      return response.json();
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: ['dynamodb', 'tables', variables.tenantId],
      });
    },
  });
}

export function useTableItems(tableName: string | null, tenantId: string | null) {
  return useQuery<ScanItemsResponse>({
    queryKey: ['dynamodb', 'items', tableName, tenantId],
    queryFn: async () => {
      if (!tableName || !tenantId) throw new Error('Table name and tenant ID required');

      const response = await fetch(
        `${API_BASE}/resources/dynamodb/tables/${tableName}/items?tenant_id=${tenantId}&limit=100`,
        {
          headers: { 'X-Tenant-ID': tenantId },
        }
      );

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to fetch items');
      }

      return response.json();
    },
    enabled: !!tableName && !!tenantId,
  });
}

export function usePutItem() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      tableName,
      tenantId,
      item,
    }: {
      tableName: string;
      tenantId: string;
      item: Record<string, any>;
    }) => {
      const response = await fetch(
        `${API_BASE}/resources/dynamodb/tables/${tableName}/items`,
        {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
            'X-Tenant-ID': tenantId,
          },
          body: JSON.stringify({ tenant_id: tenantId, item }),
        }
      );

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to put item');
      }

      return response.json();
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: ['dynamodb', 'items', variables.tableName, variables.tenantId],
      });
    },
  });
}

export function useDeleteItem() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      tableName,
      tenantId,
      key,
    }: {
      tableName: string;
      tenantId: string;
      key: Record<string, any>;
    }) => {
      const response = await fetch(
        `${API_BASE}/resources/dynamodb/tables/${tableName}/items`,
        {
          method: 'DELETE',
          headers: {
            'Content-Type': 'application/json',
            'X-Tenant-ID': tenantId,
          },
          body: JSON.stringify({ tenant_id: tenantId, key }),
        }
      );

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to delete item');
      }

      return response.json();
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: ['dynamodb', 'items', variables.tableName, variables.tenantId],
      });
    },
  });
}
