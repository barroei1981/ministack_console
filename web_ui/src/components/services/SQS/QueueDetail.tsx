import React, { useMemo, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useParams, useNavigate } from 'react-router-dom';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

export const QueueDetail: React.FC = () => {
  const { queueName } = useParams<{ queueName: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [messageBody, setMessageBody] = useState('');

  const tenantId = useMemo(() => {
    const params = new URLSearchParams(window.location.search);
    return params.get('tenant_id') || '000000000001';
  }, []);

  const { data: queue } = useQuery({
    queryKey: ['sqs-queue', tenantId, queueName],
    queryFn: async () => {
      const response = await fetch(
        `${API_BASE_URL}/resources/sqs/queues/${queueName}?tenant_id=${tenantId}`
      );
      if (!response.ok) throw new Error('Failed to fetch queue');
      return response.json();
    },
    enabled: !!queueName,
  });

  const sendMutation = useMutation({
    mutationFn: async (body: string) => {
      const response = await fetch(
        `${API_BASE_URL}/resources/sqs/queues/${queueName}/messages?message_body=${encodeURIComponent(body)}&tenant_id=${tenantId}`,
        { method: 'POST' }
      );
      if (!response.ok) throw new Error('Failed to send message');
      return response.json();
    },
    onSuccess: () => {
      setMessageBody('');
      queryClient.invalidateQueries({ queryKey: ['sqs-queue', tenantId, queueName] });
    },
  });

  return (
    <div style={{ padding: '20px' }}>
      <button onClick={() => navigate(-1)} style={{ marginBottom: '20px', padding: '8px 16px', border: '1px solid #ddd', borderRadius: '4px', backgroundColor: 'white', cursor: 'pointer' }}>
        ← Back to Queues
      </button>

      <h2>{queueName}</h2>

      <div style={{ marginTop: '20px', padding: '20px', border: '1px solid #ddd', borderRadius: '8px', backgroundColor: 'white' }}>
        <h3 style={{ marginTop: 0 }}>Send Message</h3>
        <textarea value={messageBody} onChange={(e) => setMessageBody(e.target.value)} placeholder="Message body..." style={{ width: '100%', minHeight: '100px', padding: '8px', border: '1px solid #ddd', borderRadius: '4px', fontFamily: 'monospace', fontSize: '14px' }} />
        <button onClick={() => sendMutation.mutate(messageBody)} disabled={!messageBody || sendMutation.isPending} style={{ marginTop: '12px', padding: '8px 24px', backgroundColor: messageBody ? '#FF9900' : '#ccc', color: 'white', border: 'none', borderRadius: '4px', cursor: messageBody ? 'pointer' : 'not-allowed' }}>
          {sendMutation.isPending ? 'Sending...' : 'Send Message'}
        </button>
      </div>

      {queue && (
        <div style={{ marginTop: '20px', padding: '20px', border: '1px solid #ddd', borderRadius: '8px', backgroundColor: 'white' }}>
          <h3 style={{ marginTop: 0 }}>Queue Details</h3>
          <div style={{ display: 'grid', gridTemplateColumns: '200px 1fr', gap: '12px', fontSize: '14px' }}>
            <div style={{ fontWeight: 500 }}>Queue URL:</div>
            <div style={{ fontFamily: 'monospace', fontSize: '13px', wordBreak: 'break-all' }}>{queue.queue_url}</div>
            <div style={{ fontWeight: 500 }}>Messages:</div>
            <div>{queue.message_count || 0}</div>
          </div>
        </div>
      )}
    </div>
  );
};
