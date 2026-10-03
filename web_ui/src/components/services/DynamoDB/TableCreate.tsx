import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../../common/Button';
import { useCreateTable } from '../../../hooks/useDynamoDB';
import type {
  AttributeDefinition,
  KeySchemaElement,
  ProvisionedThroughput,
} from '../../../types/dynamodb';
import { ATTRIBUTE_TYPES, BILLING_MODES } from '../../../types/dynamodb';

export function TableCreate() {
  const navigate = useNavigate();
  const createTableMutation = useCreateTable();

  // Get tenant_id from URL query params
  const tenantId = useMemo(() => {
    const params = new URLSearchParams(window.location.search);
    return params.get('tenant_id');
  }, []);

  const [tableName, setTableName] = useState('');
  const [partitionKeyName, setPartitionKeyName] = useState('');
  const [partitionKeyType, setPartitionKeyType] = useState<'S' | 'N' | 'B'>('S');
  const [sortKeyEnabled, setSortKeyEnabled] = useState(false);
  const [sortKeyName, setSortKeyName] = useState('');
  const [sortKeyType, setSortKeyType] = useState<'S' | 'N' | 'B'>('S');
  const [billingMode, setBillingMode] = useState<'PAY_PER_REQUEST' | 'PROVISIONED'>(
    'PAY_PER_REQUEST'
  );
  const [readCapacity, setReadCapacity] = useState('5');
  const [writeCapacity, setWriteCapacity] = useState('5');
  const [project, setProject] = useState('');

  const [errors, setErrors] = useState<Record<string, string>>({});

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!tableName) {
      newErrors.tableName = 'Table name is required';
    } else if (tableName.length < 3 || tableName.length > 255) {
      newErrors.tableName = 'Table name must be 3-255 characters';
    } else if (!/^[a-zA-Z0-9_.-]+$/.test(tableName)) {
      newErrors.tableName = 'Table name must contain only alphanumeric, underscores, hyphens, and periods';
    }

    if (!partitionKeyName) {
      newErrors.partitionKeyName = 'Partition key name is required';
    }

    if (sortKeyEnabled && !sortKeyName) {
      newErrors.sortKeyName = 'Sort key name is required when enabled';
    }

    if (sortKeyEnabled && partitionKeyName === sortKeyName) {
      newErrors.sortKeyName = 'Sort key must be different from partition key';
    }

    if (billingMode === 'PROVISIONED') {
      const readCap = parseInt(readCapacity, 10);
      const writeCap = parseInt(writeCapacity, 10);

      if (isNaN(readCap) || readCap < 1) {
        newErrors.readCapacity = 'Read capacity must be at least 1';
      }
      if (isNaN(writeCap) || writeCap < 1) {
        newErrors.writeCapacity = 'Write capacity must be at least 1';
      }
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateForm() || !tenantId) return;

    const keySchema: KeySchemaElement[] = [
      { AttributeName: partitionKeyName, KeyType: 'HASH' },
    ];

    const attributeDefinitions: AttributeDefinition[] = [
      { AttributeName: partitionKeyName, AttributeType: partitionKeyType },
    ];

    if (sortKeyEnabled && sortKeyName) {
      keySchema.push({ AttributeName: sortKeyName, KeyType: 'RANGE' });
      attributeDefinitions.push({
        AttributeName: sortKeyName,
        AttributeType: sortKeyType,
      });
    }

    let provisionedThroughput: ProvisionedThroughput | undefined;
    if (billingMode === 'PROVISIONED') {
      provisionedThroughput = {
        ReadCapacityUnits: parseInt(readCapacity, 10),
        WriteCapacityUnits: parseInt(writeCapacity, 10),
      };
    }

    try {
      await createTableMutation.mutateAsync({
        name: tableName,
        key_schema: keySchema,
        attribute_definitions: attributeDefinitions,
        billing_mode: billingMode,
        provisioned_throughput: provisionedThroughput,
        tenant_id: tenantId,
        project: project || undefined,
      });

      navigate(`/dynamodb/tables?tenant_id=${tenantId}`);
    } catch (error) {
      console.error('Create table failed:', error);
      setErrors({ submit: (error as Error).message });
    }
  };

  if (!tenantId) {
    return (
      <div className="p-8 text-center text-gray-600">
        Please select a tenant to create a table
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-gray-900">Create DynamoDB table</h1>
        <p className="mt-1 text-sm text-gray-600">
          Create a new DynamoDB table with partition key and optional sort key
        </p>
      </div>

      <form onSubmit={handleSubmit} className="max-w-2xl space-y-6">
        <div className="rounded-lg border border-gray-200 bg-white p-6">
          <h2 className="mb-4 text-lg font-medium text-gray-900">Table details</h2>

          <div className="space-y-4">
            <div>
              <label htmlFor="tableName" className="block text-sm font-medium text-gray-700">
                Table name *
              </label>
              <input
                id="tableName"
                type="text"
                value={tableName}
                onChange={(e) => setTableName(e.target.value)}
                className={`mt-1 w-full rounded border px-3 py-2 focus:outline-none ${
                  errors.tableName
                    ? 'border-red-500 focus:border-red-500'
                    : 'border-gray-300 focus:border-blue-500'
                }`}
                placeholder="my-table"
              />
              {errors.tableName && (
                <p className="mt-1 text-sm text-red-600">{errors.tableName}</p>
              )}
            </div>

            <div>
              <label htmlFor="project" className="block text-sm font-medium text-gray-700">
                Project (optional)
              </label>
              <input
                id="project"
                type="text"
                value={project}
                onChange={(e) => setProject(e.target.value)}
                className="mt-1 w-full rounded border border-gray-300 px-3 py-2 focus:border-blue-500 focus:outline-none"
                placeholder="my-project"
              />
            </div>
          </div>
        </div>

        <div className="rounded-lg border border-gray-200 bg-white p-6">
          <h2 className="mb-4 text-lg font-medium text-gray-900">Partition key</h2>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label htmlFor="partitionKeyName" className="block text-sm font-medium text-gray-700">
                Partition key name *
              </label>
              <input
                id="partitionKeyName"
                type="text"
                value={partitionKeyName}
                onChange={(e) => setPartitionKeyName(e.target.value)}
                className={`mt-1 w-full rounded border px-3 py-2 focus:outline-none ${
                  errors.partitionKeyName
                    ? 'border-red-500 focus:border-red-500'
                    : 'border-gray-300 focus:border-blue-500'
                }`}
                placeholder="id"
              />
              {errors.partitionKeyName && (
                <p className="mt-1 text-sm text-red-600">{errors.partitionKeyName}</p>
              )}
            </div>

            <div>
              <label htmlFor="partitionKeyType" className="block text-sm font-medium text-gray-700">
                Type *
              </label>
              <select
                id="partitionKeyType"
                value={partitionKeyType}
                onChange={(e) => setPartitionKeyType(e.target.value as 'S' | 'N' | 'B')}
                className="mt-1 w-full rounded border border-gray-300 px-3 py-2 focus:border-blue-500 focus:outline-none"
              >
                {ATTRIBUTE_TYPES.map((type) => (
                  <option key={type.value} value={type.value}>
                    {type.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        <div className="rounded-lg border border-gray-200 bg-white p-6">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-medium text-gray-900">Sort key</h2>
            <label className="flex items-center">
              <input
                type="checkbox"
                checked={sortKeyEnabled}
                onChange={(e) => setSortKeyEnabled(e.target.checked)}
                className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              <span className="ml-2 text-sm text-gray-700">Add sort key</span>
            </label>
          </div>

          {sortKeyEnabled && (
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label htmlFor="sortKeyName" className="block text-sm font-medium text-gray-700">
                  Sort key name *
                </label>
                <input
                  id="sortKeyName"
                  type="text"
                  value={sortKeyName}
                  onChange={(e) => setSortKeyName(e.target.value)}
                  className={`mt-1 w-full rounded border px-3 py-2 focus:outline-none ${
                    errors.sortKeyName
                      ? 'border-red-500 focus:border-red-500'
                      : 'border-gray-300 focus:border-blue-500'
                  }`}
                  placeholder="timestamp"
                />
                {errors.sortKeyName && (
                  <p className="mt-1 text-sm text-red-600">{errors.sortKeyName}</p>
                )}
              </div>

              <div>
                <label htmlFor="sortKeyType" className="block text-sm font-medium text-gray-700">
                  Type *
                </label>
                <select
                  id="sortKeyType"
                  value={sortKeyType}
                  onChange={(e) => setSortKeyType(e.target.value as 'S' | 'N' | 'B')}
                  className="mt-1 w-full rounded border border-gray-300 px-3 py-2 focus:border-blue-500 focus:outline-none"
                >
                  {ATTRIBUTE_TYPES.map((type) => (
                    <option key={type.value} value={type.value}>
                      {type.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          )}
        </div>

        <div className="rounded-lg border border-gray-200 bg-white p-6">
          <h2 className="mb-4 text-lg font-medium text-gray-900">Table settings</h2>

          <div className="space-y-4">
            <div>
              <label htmlFor="billingMode" className="block text-sm font-medium text-gray-700">
                Billing mode *
              </label>
              <select
                id="billingMode"
                value={billingMode}
                onChange={(e) =>
                  setBillingMode(e.target.value as 'PAY_PER_REQUEST' | 'PROVISIONED')
                }
                className="mt-1 w-full rounded border border-gray-300 px-3 py-2 focus:border-blue-500 focus:outline-none"
              >
                {BILLING_MODES.map((mode) => (
                  <option key={mode.value} value={mode.value}>
                    {mode.label}
                  </option>
                ))}
              </select>
              <p className="mt-1 text-sm text-gray-600">
                {billingMode === 'PAY_PER_REQUEST'
                  ? 'Pay per request - no need to specify capacity'
                  : 'Provisioned - specify read and write capacity units'}
              </p>
            </div>

            {billingMode === 'PROVISIONED' && (
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label htmlFor="readCapacity" className="block text-sm font-medium text-gray-700">
                    Read capacity units *
                  </label>
                  <input
                    id="readCapacity"
                    type="number"
                    min="1"
                    value={readCapacity}
                    onChange={(e) => setReadCapacity(e.target.value)}
                    className={`mt-1 w-full rounded border px-3 py-2 focus:outline-none ${
                      errors.readCapacity
                        ? 'border-red-500 focus:border-red-500'
                        : 'border-gray-300 focus:border-blue-500'
                    }`}
                  />
                  {errors.readCapacity && (
                    <p className="mt-1 text-sm text-red-600">{errors.readCapacity}</p>
                  )}
                </div>

                <div>
                  <label htmlFor="writeCapacity" className="block text-sm font-medium text-gray-700">
                    Write capacity units *
                  </label>
                  <input
                    id="writeCapacity"
                    type="number"
                    min="1"
                    value={writeCapacity}
                    onChange={(e) => setWriteCapacity(e.target.value)}
                    className={`mt-1 w-full rounded border px-3 py-2 focus:outline-none ${
                      errors.writeCapacity
                        ? 'border-red-500 focus:border-red-500'
                        : 'border-gray-300 focus:border-blue-500'
                    }`}
                  />
                  {errors.writeCapacity && (
                    <p className="mt-1 text-sm text-red-600">{errors.writeCapacity}</p>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>

        {errors.submit && (
          <div className="rounded border border-red-500 bg-red-50 p-4 text-sm text-red-600">
            {errors.submit}
          </div>
        )}

        <div className="flex justify-end gap-3">
          <Button
            type="button"
            variant="secondary"
            onClick={() => navigate(`/dynamodb/tables?tenant_id=${tenantId}`)}
          >
            Cancel
          </Button>
          <Button
            type="submit"
            variant="primary"
            disabled={createTableMutation.isPending}
          >
            {createTableMutation.isPending ? 'Creating...' : 'Create table'}
          </Button>
        </div>
      </form>
    </div>
  );
}
