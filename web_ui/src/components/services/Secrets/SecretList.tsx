import React, { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

export const SecretList: React.FC = () => {
  const tenantId = useMemo(() => {
    const params = new URLSearchParams(window.location.search);
    return params.get('tenant_id') || '000000000001';
  }, []);

  const { data, isLoading, error } = useQuery({
    queryKey: ['secrets', tenantId],
    queryFn: async () => {
      const response = await fetch(`${API_BASE_URL}/resources/secrets?tenant_id=${tenantId}`);
      if (!response.ok) throw new Error('Failed to fetch secrets');
      return response.json() as Promise<{ secrets: any[] }>;
    },
    refetchInterval: 10000,
  });

  if (isLoading) return <div style={{ padding: '20px' }}><h2>Secrets Manager</h2><p>Loading...</p></div>;
  if (error) return <div style={{ padding: '20px' }}><h2>Secrets Manager</h2><p style={{ color: 'red' }}>Error: {(error as Error).message}</p></div>;

  const secrets = data?.secrets || [];

  return (
    <div style={{ padding: '20px' }}>
      <h2>Secrets Manager</h2>
      {secrets.length === 0 ? (
        <div style={{ padding: '40px', textAlign: 'center', backgroundColor: '#f5f5f5', borderRadius: '8px' }}>
          <p style={{ color: '#666' }}>No secrets found.</p>
        </div>
      ) : (
        <div style={{ display: 'grid', gap: '12px' }}>
          {secrets.map((secret: any, i: number) => (
            <div key={i} style={{ border: '1px solid #ddd', borderRadius: '8px', padding: '16px', backgroundColor: 'white' }}>
              <div style={{ fontWeight: 600 }}>{secret.name || 'Secret'}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
