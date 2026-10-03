import { useState, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Button } from '../../common/Button';
import { useTables } from '../../../hooks/useDynamoDB';
import { ItemBrowser } from './ItemBrowser';
import type { DynamoDBTable } from '../../../types/dynamodb';

type TabType = 'overview' | 'items';

export function TableDetail() {
  const { tableName } = useParams<{ tableName: string }>();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<TabType>('overview');

  // Get tenant_id from URL query params
  const tenantId = useMemo(() => {
    const params = new URLSearchParams(window.location.search);
    return params.get('tenant_id') || '000000000001'; // Default tenant
  }, []);

  const { data: response, isLoading } = useTables(tenantId);

  if (!tableName) {
    return (
      <div className="p-8 text-center text-gray-600">
        Invalid table name
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="p-8 text-center text-gray-600">
        Loading table details...
      </div>
    );
  }

  const table = response?.tables.find((t: DynamoDBTable) => t.name === tableName);

  if (!table) {
    return (
      <div className="p-8 text-center text-gray-600">
        Table not found
      </div>
    );
  }

  const getKeyType = (attributeName: string): string => {
    const attrDef = table.attribute_definitions.find(
      (a) => a.AttributeName === attributeName
    );
    if (!attrDef) return 'String';
    return attrDef.AttributeType === 'S' ? 'String' : attrDef.AttributeType === 'N' ? 'Number' : 'Binary';
  };

  const partitionKey = table.key_schema.find((k) => k.KeyType === 'HASH');
  const sortKey = table.key_schema.find((k) => k.KeyType === 'RANGE');

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="border-b border-gray-200 bg-white">
        <div className="px-6 py-4">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <Button
                variant="secondary"
                onClick={() => navigate(`/dynamodb/tables?tenant_id=${tenantId}`)}
              >
                ← Back to tables
              </Button>
            </div>
          </div>

          <h1 className="text-2xl font-semibold text-gray-900">{tableName}</h1>
          <p className="mt-1 text-sm text-gray-600">{table.arn}</p>

          <div className="mt-6 flex gap-6 border-b border-gray-200">
            <button
              onClick={() => setActiveTab('overview')}
              className={`border-b-2 px-1 pb-3 text-sm font-medium ${
                activeTab === 'overview'
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-gray-600 hover:border-gray-300 hover:text-gray-900'
              }`}
            >
              Overview
            </button>
            <button
              onClick={() => setActiveTab('items')}
              className={`border-b-2 px-1 pb-3 text-sm font-medium ${
                activeTab === 'items'
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-gray-600 hover:border-gray-300 hover:text-gray-900'
              }`}
            >
              Items
            </button>
          </div>
        </div>
      </div>

      <div className="p-6">
        {activeTab === 'overview' && (
          <div className="space-y-6">
            <div className="rounded-lg border border-gray-200 bg-white p-6">
              <h2 className="mb-4 text-lg font-medium text-gray-900">Table details</h2>
              <dl className="grid grid-cols-2 gap-4">
                <div>
                  <dt className="text-sm font-medium text-gray-600">Status</dt>
                  <dd className="mt-1 text-sm text-gray-900">{table.table_status}</dd>
                </div>
                <div>
                  <dt className="text-sm font-medium text-gray-600">Created</dt>
                  <dd className="mt-1 text-sm text-gray-900">
                    {new Date(table.created_at).toLocaleString()}
                  </dd>
                </div>
                <div>
                  <dt className="text-sm font-medium text-gray-600">Billing mode</dt>
                  <dd className="mt-1 text-sm text-gray-900">
                    {table.billing_mode === 'PAY_PER_REQUEST' ? 'On-demand' : 'Provisioned'}
                  </dd>
                </div>
                <div>
                  <dt className="text-sm font-medium text-gray-600">Item count</dt>
                  <dd className="mt-1 text-sm text-gray-900">
                    {table.item_count.toLocaleString()}
                  </dd>
                </div>
              </dl>
            </div>

            <div className="rounded-lg border border-gray-200 bg-white p-6">
              <h2 className="mb-4 text-lg font-medium text-gray-900">Primary key</h2>
              <dl className="space-y-4">
                <div>
                  <dt className="text-sm font-medium text-gray-600">Partition key</dt>
                  <dd className="mt-1 text-sm text-gray-900">
                    {partitionKey ? `${partitionKey.AttributeName} (${getKeyType(partitionKey.AttributeName)})` : '-'}
                  </dd>
                </div>
                {sortKey && (
                  <div>
                    <dt className="text-sm font-medium text-gray-600">Sort key</dt>
                    <dd className="mt-1 text-sm text-gray-900">
                      {`${sortKey.AttributeName} (${getKeyType(sortKey.AttributeName)})`}
                    </dd>
                  </div>
                )}
              </dl>
            </div>

            {table.project && (
              <div className="rounded-lg border border-gray-200 bg-white p-6">
                <h2 className="mb-4 text-lg font-medium text-gray-900">Project</h2>
                <p className="text-sm text-gray-900">{table.project}</p>
              </div>
            )}
          </div>
        )}

        {activeTab === 'items' && (
          <ItemBrowser tableName={tableName} tenantId={tenantId} table={table} />
        )}
      </div>
    </div>
  );
}
