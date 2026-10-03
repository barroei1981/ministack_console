import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../../common/Button';
import { Table } from '../../common/Table';
import { Modal } from '../../common/Modal';
import { useTables, useDeleteTable } from '../../../hooks/useDynamoDB';
import { useSSE } from '../../../hooks/useSSE';
import type { DynamoDBTable } from '../../../types/dynamodb';

export function TableList() {
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [tableToDelete, setTableToDelete] = useState<string | null>(null);

  // Get tenant_id from URL query params
  const tenantId = useMemo(() => {
    const params = new URLSearchParams(window.location.search);
    return params.get('tenant_id');
  }, []);

  const { data: response, isLoading } = useTables(tenantId);
  const deleteTableMutation = useDeleteTable();

  // SSE for real-time updates
  useSSE(tenantId);

  const tables = response?.tables || [];

  const filteredTables = tables.filter((table) =>
    table.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleDeleteClick = (tableName: string) => {
    setTableToDelete(tableName);
    setDeleteModalOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!tableToDelete || !tenantId) return;

    try {
      await deleteTableMutation.mutateAsync({
        tableName: tableToDelete,
        tenantId,
      });
      setDeleteModalOpen(false);
      setTableToDelete(null);
    } catch (error) {
      console.error('Delete failed:', error);
    }
  };

  const getPartitionKey = (table: DynamoDBTable): string => {
    const hashKey = table.key_schema.find((k) => k.KeyType === 'HASH');
    if (!hashKey) return '-';

    const attrDef = table.attribute_definitions.find(
      (a) => a.AttributeName === hashKey.AttributeName
    );
    const typeLabel = attrDef?.AttributeType === 'S' ? 'String' : attrDef?.AttributeType === 'N' ? 'Number' : 'Binary';
    return `${hashKey.AttributeName} (${typeLabel})`;
  };

  const getSortKey = (table: DynamoDBTable): string => {
    const rangeKey = table.key_schema.find((k) => k.KeyType === 'RANGE');
    if (!rangeKey) return '-';

    const attrDef = table.attribute_definitions.find(
      (a) => a.AttributeName === rangeKey.AttributeName
    );
    const typeLabel = attrDef?.AttributeType === 'S' ? 'String' : attrDef?.AttributeType === 'N' ? 'Number' : 'Binary';
    return `${rangeKey.AttributeName} (${typeLabel})`;
  };

  const columns = [
    {
      key: 'name',
      label: 'Table name',
      render: (table: DynamoDBTable) => (
        <button
          onClick={() => navigate(`/dynamodb/tables/${table.name}`)}
          className="text-blue-600 hover:underline font-medium"
        >
          {table.name}
        </button>
      ),
    },
    {
      key: 'partition_key',
      label: 'Partition key',
      render: (table: DynamoDBTable) => (
        <span className="text-gray-900">{getPartitionKey(table)}</span>
      ),
    },
    {
      key: 'sort_key',
      label: 'Sort key',
      render: (table: DynamoDBTable) => (
        <span className="text-gray-600">{getSortKey(table)}</span>
      ),
    },
    {
      key: 'item_count',
      label: 'Item count',
      render: (table: DynamoDBTable) => (
        <span className="text-gray-900">{table.item_count.toLocaleString()}</span>
      ),
    },
    {
      key: 'created',
      label: 'Created',
      render: (table: DynamoDBTable) => (
        <span className="text-gray-600">
          {new Date(table.created_at).toLocaleDateString()}
        </span>
      ),
    },
    {
      key: 'actions',
      label: 'Actions',
      render: (table: DynamoDBTable) => (
        <Button
          variant="secondary"
          onClick={() => handleDeleteClick(table.name)}
          disabled={deleteTableMutation.isPending}
        >
          Delete
        </Button>
      ),
    },
  ];

  if (!tenantId) {
    return (
      <div className="p-8 text-center text-gray-600">
        Please select a tenant to view tables
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Tables</h1>
          <p className="mt-1 text-sm text-gray-600">
            {tables.length} {tables.length === 1 ? 'table' : 'tables'}
          </p>
        </div>
        <Button variant="primary" onClick={() => navigate('/dynamodb/create')}>
          Create table
        </Button>
      </div>

      <div className="mb-4">
        <input
          type="text"
          placeholder="Search tables..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full max-w-md rounded border border-gray-300 px-3 py-2 focus:border-blue-500 focus:outline-none"
        />
      </div>

      {isLoading ? (
        <div className="flex h-64 items-center justify-center">
          <div className="text-gray-600">Loading tables...</div>
        </div>
      ) : filteredTables.length === 0 ? (
        <div className="rounded-lg border border-gray-200 bg-white p-8 text-center">
          <h3 className="mb-2 text-lg font-medium text-gray-900">
            {searchQuery ? 'No matching tables' : 'No tables'}
          </h3>
          <p className="mb-4 text-gray-600">
            {searchQuery
              ? 'Try adjusting your search query'
              : 'Create your first DynamoDB table to get started'}
          </p>
          {!searchQuery && (
            <Button variant="primary" onClick={() => navigate('/dynamodb/create')}>
              Create table
            </Button>
          )}
        </div>
      ) : (
        <Table columns={columns} data={filteredTables} />
      )}

      <Modal
        isOpen={deleteModalOpen}
        onClose={() => setDeleteModalOpen(false)}
        title="Delete table"
      >
        <div className="space-y-4">
          <p className="text-gray-700">
            Are you sure you want to delete table <strong>{tableToDelete}</strong>?
          </p>
          <p className="text-sm text-red-600">
            This action cannot be undone. All items in the table will be lost.
          </p>
          <div className="flex justify-end gap-3">
            <Button variant="secondary" onClick={() => setDeleteModalOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              onClick={handleDeleteConfirm}
              disabled={deleteTableMutation.isPending}
            >
              {deleteTableMutation.isPending ? 'Deleting...' : 'Delete'}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
