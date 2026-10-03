import React, { useMemo, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

interface SQSQueue {
  id: string;
  name: string;
  queue_url: string;
  message_count: number;
  tenant_id: string;
}

export const QueueList: React.FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [newQueueName, setNewQueueName] = useState('');
  const [showCreateForm, setShowCreateForm] = useState(false);

  const tenantId = useMemo(() => {
    const params = new URLSearchParams(window.location.search);
    return params.get('tenant_id') || '000000000001';
  }, []);

  const { data: queues, isLoading, error } = useQuery({
    queryKey: ['sqs-queues', tenantId],
    queryFn: async () => {
      const response = await fetch(
        `${API_BASE_URL}/resources/sqs/queues?tenant_id=${tenantId}`
      );
      if (!response.ok) throw new Error('Failed to fetch queues');
      return response.json() as Promise<SQSQueue[]>;
    },
    refetchInterval: 10000,
  });

  const createMutation = useMutation({
    mutationFn: async (queueName: string) => {
      const response = await fetch(
        `${API_BASE_URL}/resources/sqs/queues?queue_name=${encodeURIComponent(queueName)}&tenant_id=${tenantId}`,
        { method: 'POST' }
      );
      if (!response.ok) throw new Error('Failed to create queue');
      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sqs-queues', tenantId] });
      setShowCreateForm(false);
      setNewQueueName('');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (queueUrl: string) => {
      const response = await fetch(
        `${API_BASE_URL}/resources/sqs/queues?queue_url=${encodeURIComponent(queueUrl)}&tenant_id=${tenantId}`,
        { method: 'DELETE' }
      );
      if (!response.ok) throw new Error('Failed to delete queue');
      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sqs-queues', tenantId] });
    },
  });

  if (isLoading) {
    return <div style={{ padding: '20px' }}><h2>SQS Queues</h2><p>Loading...</p></div>;
  }

  if (error) {
    return <div style={{ padding: '20px' }}><h2>SQS Queues</h2><p style={{ color: 'red' }}>Error: {(error as Error).message}</p></div>;
  }

  return (
    <div style={{ padding: '20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <h2>SQS Queues</h2>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <div style={{ fontSize: '14px', color: '#666' }}>Tenant: {tenantId}</div>
          <button onClick={() => setShowCreateForm(!showCreateForm)} style={{ padding: '8px 16px', backgroundColor: '#FF9900', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 500 }}>
            {showCreateForm ? 'Cancel' : '+ Create Queue'}
          </button>
        </div>
      </div>

      {showCreateForm && (
        <div style={{ marginBottom: '20px', padding: '20px', border: '1px solid #ddd', borderRadius: '8px', backgroundColor: '#f9f9f9' }}>
          <h3 style={{ marginTop: 0, marginBottom: '12px', fontSize: '16px' }}>Create Queue</h3>
          <div style={{ display: 'flex', gap: '12px' }}>
            <input type="text" value={newQueueName} onChange={(e) => setNewQueueName(e.target.value)} placeholder="queue-name" style={{ flex: 1, padding: '8px 12px', border: '1px solid #ddd', borderRadius: '4px', fontSize: '14px' }} />
            <button onClick={() => createMutation.mutate(newQueueName)} disabled={!newQueueName || createMutation.isPending} style={{ padding: '8px 24px', backgroundColor: newQueueName ? '#FF9900' : '#ccc', color: 'white', border: 'none', borderRadius: '4px', cursor: newQueueName ? 'pointer' : 'not-allowed', fontWeight: 500 }}>
              {createMutation.isPending ? 'Creating...' : 'Create'}
            </button>
          </div>
        </div>
      )}

      {!queues || queues.length === 0 ? (
        <div style={{ padding: '40px', textAlign: 'center', backgroundColor: '#f5f5f5', borderRadius: '8px' }}>
          <p style={{ color: '#666', margin: 0 }}>No queues found. Create one to get started.</p>
        </div>
      ) : (
        <div style={{ display: 'grid', gap: '12px' }}>
          {queues.map((queue) => (
            <div key={queue.id} style={{ border: '1px solid #ddd', borderRadius: '8px', padding: '16px', backgroundColor: 'white', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ flex: 1, cursor: 'pointer' }} onClick={() => navigate(`/sqs/queues/${encodeURIComponent(queue.name)}?tenant_id=${tenantId}`)}>
                <div style={{ fontSize: '16px', fontWeight: 600, color: '#232F3E', marginBottom: '4px' }}>{queue.name}</div>
                <div style={{ fontSize: '13px', color: '#666' }}>Messages: {queue.message_count}</div>
              </div>
              <button onClick={() => deleteMutation.mutate(queue.queue_url)} disabled={deleteMutation.isPending} style={{ padding: '6px 12px', backgroundColor: '#d32f2f', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '14px' }}>
                {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
