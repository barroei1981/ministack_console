import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import client from '../api/client';
import type {
  CreateTableRequest,
  ScanItemsResponse,
  TableListResponse,
} from '../types/dynamodb';

export function useTables(tenantId: string | null) {
  return useQuery<TableListResponse>({
    queryKey: ['dynamodb', 'tables', tenantId],
    queryFn: async () => {
      if (!tenantId) {
        return { tables: [], tenant_id: '', total: 0 };
      }
      const response = await client.get<TableListResponse>(
        '/resources/dynamodb/tables',
        { params: { tenant_id: tenantId } }
      );
      return response.data;
    },
    enabled: !!tenantId,
  });
}

export function useCreateTable() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (request: CreateTableRequest) => {
      const response = await client.post('/resources/dynamodb/tables', request);
      return response.data;
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
      const response = await client.delete(
        `/resources/dynamodb/tables/${tableName}`,
        { params: { tenant_id: tenantId } }
      );
      return response.data;
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
      if (!tableName || !tenantId) {
        return { items: [], count: 0, scanned_count: 0 };
      }
      const response = await client.get<ScanItemsResponse>(
        `/resources/dynamodb/tables/${tableName}/items`,
        { params: { tenant_id: tenantId, limit: 100 } }
      );
      return response.data;
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
      const response = await client.put(
        `/resources/dynamodb/tables/${tableName}/items`,
        { tenant_id: tenantId, item }
      );
      return response.data;
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
      const response = await client.delete(
        `/resources/dynamodb/tables/${tableName}/items`,
        { data: { tenant_id: tenantId, key } }
      );
      return response.data;
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: ['dynamodb', 'items', variables.tableName, variables.tenantId],
      });
    },
  });
}
