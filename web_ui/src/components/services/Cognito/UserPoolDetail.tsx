import React, { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useParams, useNavigate } from 'react-router-dom';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

interface UserPoolDetail {
  Id: string;
  Name: string;
  Status?: string;
  CreationDate?: string;
  LastModifiedDate?: string;
  EstimatedNumberOfUsers?: number;
  MfaConfiguration?: string;
  UserPoolTags?: Record<string, string>;
}

export const UserPoolDetail: React.FC = () => {
  const { poolId } = useParams<{ poolId: string }>();
  const navigate = useNavigate();

  const tenantId = useMemo(() => {
    const params = new URLSearchParams(window.location.search);
    return params.get('tenant_id') || '000000000001';
  }, []);

  const { data: pool, isLoading, error } = useQuery({
    queryKey: ['cognito-pool-detail', tenantId, poolId],
    queryFn: async () => {
      const response = await fetch(
        `${API_BASE_URL}/resources/cognito/user-pools/${poolId}?tenant_id=${tenantId}`
      );
      if (!response.ok) {
        throw new Error('Failed to fetch user pool details');
      }
      return response.json() as Promise<UserPoolDetail>;
    },
    enabled: !!poolId,
  });

  if (isLoading) {
    return (
      <div style={{ padding: '20px' }}>
        <button onClick={() => navigate(-1)} style={{ marginBottom: '20px' }}>
          ← Back to User Pools
        </button>
        <p>Loading user pool details...</p>
      </div>
    );
  }

  if (error || !pool) {
    return (
      <div style={{ padding: '20px' }}>
        <button onClick={() => navigate(-1)} style={{ marginBottom: '20px' }}>
          ← Back to User Pools
        </button>
        <p style={{ color: 'red' }}>
          Error: {error ? (error as Error).message : 'User pool not found'}
        </p>
      </div>
    );
  }

  return (
    <div style={{ padding: '20px' }}>
      <button
        onClick={() => navigate(-1)}
        style={{
          marginBottom: '20px',
          padding: '8px 16px',
          border: '1px solid #ddd',
          borderRadius: '4px',
          backgroundColor: 'white',
          cursor: 'pointer',
        }}
      >
        ← Back to User Pools
      </button>

      <div style={{ marginBottom: '24px' }}>
        <h2 style={{ margin: 0, marginBottom: '8px' }}>{pool.Name}</h2>
        <div style={{
          fontSize: '14px',
          color: '#666',
          fontFamily: 'monospace'
        }}>
          {pool.Id}
        </div>
      </div>

      <div style={{
        display: 'grid',
        gap: '16px',
      }}>
        {/* General Information */}
        <div style={{
          border: '1px solid #ddd',
          borderRadius: '8px',
          padding: '20px',
          backgroundColor: 'white',
        }}>
          <h3 style={{
            marginTop: 0,
            marginBottom: '16px',
            fontSize: '16px',
            fontWeight: 600
          }}>
            General Information
          </h3>

          <div style={{
            display: 'grid',
            gridTemplateColumns: '200px 1fr',
            gap: '12px',
            fontSize: '14px',
          }}>
            <div style={{ fontWeight: 500, color: '#545b64' }}>Status:</div>
            <div>
              <span style={{
                padding: '2px 8px',
                borderRadius: '4px',
                fontSize: '12px',
                backgroundColor: pool.Status === 'Enabled' ? '#d4edda' : '#f8d7da',
                color: pool.Status === 'Enabled' ? '#155724' : '#721c24',
              }}>
                {pool.Status || 'Unknown'}
              </span>
            </div>

            <div style={{ fontWeight: 500, color: '#545b64' }}>Pool ID:</div>
            <div style={{ fontFamily: 'monospace', fontSize: '13px' }}>
              {pool.Id}
            </div>

            {pool.CreationDate && (
              <>
                <div style={{ fontWeight: 500, color: '#545b64' }}>Created:</div>
                <div>{new Date(pool.CreationDate).toLocaleString()}</div>
              </>
            )}

            {pool.LastModifiedDate && (
              <>
                <div style={{ fontWeight: 500, color: '#545b64' }}>Last Modified:</div>
                <div>{new Date(pool.LastModifiedDate).toLocaleString()}</div>
              </>
            )}

            {pool.EstimatedNumberOfUsers !== undefined && (
              <>
                <div style={{ fontWeight: 500, color: '#545b64' }}>Estimated Users:</div>
                <div>{pool.EstimatedNumberOfUsers.toLocaleString()}</div>
              </>
            )}

            {pool.MfaConfiguration && (
              <>
                <div style={{ fontWeight: 500, color: '#545b64' }}>MFA:</div>
                <div>{pool.MfaConfiguration}</div>
              </>
            )}
          </div>
        </div>

        {/* Tags */}
        {pool.UserPoolTags && Object.keys(pool.UserPoolTags).length > 0 && (
          <div style={{
            border: '1px solid #ddd',
            borderRadius: '8px',
            padding: '20px',
            backgroundColor: 'white',
          }}>
            <h3 style={{
              marginTop: 0,
              marginBottom: '16px',
              fontSize: '16px',
              fontWeight: 600
            }}>
              Tags
            </h3>

            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))',
              gap: '8px',
              fontSize: '14px',
            }}>
              {Object.entries(pool.UserPoolTags).map(([key, value]) => (
                <div
                  key={key}
                  style={{
                    padding: '8px 12px',
                    backgroundColor: '#f5f5f5',
                    borderRadius: '4px',
                  }}
                >
                  <span style={{ fontWeight: 500, color: '#545b64' }}>{key}:</span>{' '}
                  <span>{value}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
