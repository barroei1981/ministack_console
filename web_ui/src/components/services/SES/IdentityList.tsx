import React, { useMemo, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

interface SESIdentity {
  id: string;
  name: string;
  type: string;
  verification_status: string;
  tenant_id: string;
}

export const IdentityList: React.FC = () => {
  const queryClient = useQueryClient();
  const [newEmail, setNewEmail] = useState('');
  const [showAddForm, setShowAddForm] = useState(false);

  const tenantId = useMemo(() => {
    const params = new URLSearchParams(window.location.search);
    return params.get('tenant_id') || '000000000001';
  }, []);

  const { data: identities, isLoading, error } = useQuery({
    queryKey: ['ses-identities', tenantId],
    queryFn: async () => {
      const response = await fetch(
        `${API_BASE_URL}/resources/ses/identities?tenant_id=${tenantId}`
      );
      if (!response.ok) {
        throw new Error('Failed to fetch SES identities');
      }
      return response.json() as Promise<SESIdentity[]>;
    },
    refetchInterval: 10000,
  });

  const deleteMutation = useMutation({
    mutationFn: async (identity: string) => {
      const response = await fetch(
        `${API_BASE_URL}/resources/ses/identities?identity=${encodeURIComponent(identity)}&tenant_id=${tenantId}`,
        { method: 'DELETE' }
      );
      if (!response.ok) throw new Error('Failed to delete identity');
      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ses-identities', tenantId] });
    },
  });

  const verifyMutation = useMutation({
    mutationFn: async (email: string) => {
      const response = await fetch(
        `${API_BASE_URL}/resources/ses/identities/verify?email=${encodeURIComponent(email)}&tenant_id=${tenantId}`,
        { method: 'POST' }
      );
      if (!response.ok) {
        throw new Error('Failed to send verification email');
      }
      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ses-identities', tenantId] });
      setShowAddForm(false);
      setNewEmail('');
    },
  });

  if (isLoading) {
    return (
      <div style={{ padding: '20px' }}>
        <h2>SES Verified Identities</h2>
        <p>Loading...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: '20px' }}>
        <h2>SES Verified Identities</h2>
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
        <h2>SES Verified Identities</h2>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <div style={{ fontSize: '14px', color: '#666' }}>
            Tenant: {tenantId}
          </div>
          <button
            onClick={() => setShowAddForm(!showAddForm)}
            style={{
              padding: '8px 16px',
              backgroundColor: '#FF9900',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              fontWeight: 500,
            }}
          >
            {showAddForm ? 'Cancel' : '+ Verify Email'}
          </button>
        </div>
      </div>

      {showAddForm && (
        <div style={{
          marginBottom: '20px',
          padding: '20px',
          border: '1px solid #ddd',
          borderRadius: '8px',
          backgroundColor: '#f9f9f9',
        }}>
          <h3 style={{ marginTop: 0, marginBottom: '12px', fontSize: '16px' }}>
            Verify Email Address
          </h3>
          <div style={{ display: 'flex', gap: '12px' }}>
            <input
              type="email"
              value={newEmail}
              onChange={(e) => setNewEmail(e.target.value)}
              placeholder="email@example.com"
              style={{
                flex: 1,
                padding: '8px 12px',
                border: '1px solid #ddd',
                borderRadius: '4px',
                fontSize: '14px',
              }}
            />
            <button
              onClick={() => verifyMutation.mutate(newEmail)}
              disabled={!newEmail || verifyMutation.isPending}
              style={{
                padding: '8px 24px',
                backgroundColor: newEmail ? '#FF9900' : '#ccc',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: newEmail ? 'pointer' : 'not-allowed',
                fontWeight: 500,
              }}
            >
              {verifyMutation.isPending ? 'Sending...' : 'Send Verification'}
            </button>
          </div>
          {verifyMutation.isError && (
            <p style={{ color: 'red', marginTop: '8px', fontSize: '14px' }}>
              Error: {(verifyMutation.error as Error).message}
            </p>
          )}
        </div>
      )}

      {!identities || identities.length === 0 ? (
        <div style={{
          padding: '40px',
          textAlign: 'center',
          backgroundColor: '#f5f5f5',
          borderRadius: '8px'
        }}>
          <p style={{ color: '#666', margin: 0 }}>
            No verified identities yet. Click "Verify Email" to add one.
          </p>
        </div>
      ) : (
        <div style={{
          display: 'grid',
          gap: '12px',
        }}>
          {identities.map((identity) => (
            <div
              key={identity.id}
              style={{
                border: '1px solid #ddd',
                borderRadius: '8px',
                padding: '16px',
                backgroundColor: 'white',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <div>
                <div style={{
                  fontSize: '16px',
                  fontWeight: 600,
                  color: '#232F3E',
                  marginBottom: '4px'
                }}>
                  {identity.name}
                </div>
                <div style={{
                  fontSize: '13px',
                  color: '#666',
                  fontFamily: 'monospace'
                }}>
                  {identity.id}
                </div>
              </div>

              <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                <span style={{
                  padding: '4px 12px',
                  borderRadius: '4px',
                  fontSize: '12px',
                  fontWeight: 500,
                  backgroundColor: identity.verification_status === 'Success' ? '#d4edda' :
                                  identity.verification_status === 'Pending' ? '#fff3cd' : '#f8d7da',
                  color: identity.verification_status === 'Success' ? '#155724' :
                         identity.verification_status === 'Pending' ? '#856404' : '#721c24',
                }}>
                  {identity.verification_status}
                </span>
                <button
                  onClick={() => deleteMutation.mutate(identity.name)}
                  disabled={deleteMutation.isPending}
                  style={{
                    padding: '6px 12px',
                    backgroundColor: '#d32f2f',
                    color: 'white',
                    border: 'none',
                    borderRadius: '4px',
                    cursor: 'pointer',
                    fontSize: '12px',
                  }}
                >
                  {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
