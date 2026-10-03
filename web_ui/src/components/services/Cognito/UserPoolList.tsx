import React, { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

interface UserPool {
  id: string;
  name: string;
  pool_id: string;
  status: string;
  created_at: string;
  last_modified: string;
}

export const UserPoolList: React.FC = () => {
  const navigate = useNavigate();

  const tenantId = useMemo(() => {
    const params = new URLSearchParams(window.location.search);
    return params.get('tenant_id') || '000000000001';
  }, []);

  const { data: pools, isLoading, error } = useQuery({
    queryKey: ['cognito-pools', tenantId],
    queryFn: async () => {
      const response = await fetch(
        `${API_BASE_URL}/resources/cognito/user-pools?tenant_id=${tenantId}`
      );
      if (!response.ok) {
        throw new Error('Failed to fetch user pools');
      }
      return response.json() as Promise<UserPool[]>;
    },
    refetchInterval: 10000,
  });

  if (isLoading) {
    return (
      <div style={{ padding: '20px' }}>
        <h2>Cognito User Pools</h2>
        <p>Loading...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: '20px' }}>
        <h2>Cognito User Pools</h2>
        <p style={{ color: 'red' }}>Error: {(error as Error).message}</p>
      </div>
    );
  }

  return (
    <div style={{ padding: '20px' }}>
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '20px'
      }}>
        <h2>Cognito User Pools</h2>
        <div style={{ fontSize: '14px', color: '#666' }}>
          Tenant: {tenantId}
        </div>
      </div>

      {!pools || pools.length === 0 ? (
        <div style={{
          padding: '40px',
          textAlign: 'center',
          backgroundColor: '#f5f5f5',
          borderRadius: '8px'
        }}>
          <p style={{ color: '#666', margin: 0 }}>
            No user pools found. Create one to get started.
          </p>
        </div>
      ) : (
        <div style={{
          display: 'grid',
          gap: '16px',
          gridTemplateColumns: 'repeat(auto-fill, minmax(400px, 1fr))'
        }}>
          {pools.map((pool) => (
            <div
              key={pool.pool_id}
              onClick={() => navigate(`/cognito/user-pools/${pool.pool_id}?tenant_id=${tenantId}`)}
              style={{
                border: '1px solid #ddd',
                borderRadius: '8px',
                padding: '20px',
                cursor: 'pointer',
                transition: 'all 0.2s',
                backgroundColor: 'white',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = '#FF9900';
                e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.1)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = '#ddd';
                e.currentTarget.style.boxShadow = 'none';
              }}
            >
              <div style={{ marginBottom: '12px' }}>
                <div style={{
                  fontSize: '18px',
                  fontWeight: 600,
                  color: '#232F3E',
                  marginBottom: '4px'
                }}>
                  {pool.name}
                </div>
                <div style={{
                  fontSize: '13px',
                  color: '#666',
                  fontFamily: 'monospace'
                }}>
                  {pool.pool_id}
                </div>
              </div>

              <div style={{
                display: 'grid',
                gridTemplateColumns: '120px 1fr',
                gap: '8px',
                fontSize: '14px',
                color: '#545b64'
              }}>
                <div style={{ fontWeight: 500 }}>Status:</div>
                <div>
                  <span style={{
                    padding: '2px 8px',
                    borderRadius: '4px',
                    fontSize: '12px',
                    backgroundColor: pool.status === 'Enabled' ? '#d4edda' : '#f8d7da',
                    color: pool.status === 'Enabled' ? '#155724' : '#721c24',
                  }}>
                    {pool.status}
                  </span>
                </div>

                <div style={{ fontWeight: 500 }}>Created:</div>
                <div>{new Date(pool.created_at).toLocaleDateString()}</div>

                {pool.last_modified && (
                  <>
                    <div style={{ fontWeight: 500 }}>Modified:</div>
                    <div>{new Date(pool.last_modified).toLocaleDateString()}</div>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
