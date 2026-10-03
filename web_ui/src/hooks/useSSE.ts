import { useQueryClient } from '@tanstack/react-query';
import { useEffect, useState, useRef } from 'react';
import toast from 'react-hot-toast';

interface SSEEvent {
  type: string;
  resource?: {
    type: string;
    name: string;
  };
  tenant_id: string;
}

interface SSEStatus {
  connected: boolean;
  reconnectAttempts: number;
}

const MAX_RECONNECT_ATTEMPTS = 5;
const BASE_RECONNECT_DELAY = 3000; // 3 seconds

export function useSSE(tenantId: string | null) {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<SSEStatus>({ connected: false, reconnectAttempts: 0 });
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);

  useEffect(() => {
    if (!tenantId) {
      return;
    }

    const connect = () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }

      const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:3001/api';
      const baseUrl = apiBaseUrl.replace('/api', ''); // Remove /api suffix for SSE endpoint
      const eventSource = new EventSource(`${baseUrl}/api/sse?tenant_id=${tenantId}`);
      eventSourceRef.current = eventSource;

      eventSource.onopen = () => {
        setStatus({ connected: true, reconnectAttempts: 0 });
      };

      eventSource.onmessage = (event) => {
        try {
          const data: SSEEvent = JSON.parse(event.data);

          if (data.resource?.type === 's3:bucket') {
            if (data.type === 'RESOURCE_CREATED') {
              queryClient.invalidateQueries({ queryKey: ['buckets', tenantId] });
              toast.success(`New bucket: ${data.resource.name}`, { duration: 3000 });
            } else if (data.type === 'RESOURCE_UPDATED') {
              queryClient.invalidateQueries({ queryKey: ['buckets', tenantId] });
              queryClient.invalidateQueries({ queryKey: ['bucket', data.resource.name, tenantId] });
            } else if (data.type === 'RESOURCE_DELETED') {
              queryClient.invalidateQueries({ queryKey: ['buckets', tenantId] });
            }
          } else if (data.resource?.type === 'dynamodb:table') {
            if (data.type === 'RESOURCE_CREATED') {
              queryClient.invalidateQueries({ queryKey: ['dynamodb', 'tables', tenantId] });
              toast.success(`New table: ${data.resource.name}`, { duration: 3000 });
            } else if (data.type === 'RESOURCE_UPDATED') {
              queryClient.invalidateQueries({ queryKey: ['dynamodb', 'tables', tenantId] });
              queryClient.invalidateQueries({ queryKey: ['dynamodb', 'items', data.resource.name, tenantId] });
            } else if (data.type === 'RESOURCE_DELETED') {
              queryClient.invalidateQueries({ queryKey: ['dynamodb', 'tables', tenantId] });
            }
          }
        } catch (error) {
          console.error('Failed to parse SSE event:', error);
        }
      };

      eventSource.onerror = () => {
        eventSource.close();
        setStatus((prev) => {
          const newAttempts = prev.reconnectAttempts + 1;

          if (newAttempts >= MAX_RECONNECT_ATTEMPTS) {
            toast.error('Live updates unavailable, refresh manually', {
              duration: 0,
              id: 'sse-max-attempts',
            });
            return { connected: false, reconnectAttempts: newAttempts };
          }

          // Exponential backoff
          const delay = BASE_RECONNECT_DELAY * Math.pow(2, newAttempts - 1);
          reconnectTimeoutRef.current = setTimeout(connect, delay);

          return { connected: false, reconnectAttempts: newAttempts };
        });
      };
    };

    connect();

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      toast.dismiss('sse-max-attempts');
    };
  }, [tenantId, queryClient]);

  return status;
}
