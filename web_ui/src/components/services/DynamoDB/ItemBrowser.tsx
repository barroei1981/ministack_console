import { useState } from 'react';
import { Button } from '../../common/Button';
import { Modal } from '../../common/Modal';
import { useTableItems, usePutItem, useDeleteItem } from '../../../hooks/useDynamoDB';
import type { DynamoDBTable, DynamoDBItem } from '../../../types/dynamodb';

interface ItemBrowserProps {
  tableName: string;
  tenantId: string;
  table: DynamoDBTable;
}

export function ItemBrowser({ tableName, tenantId, table }: ItemBrowserProps) {
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<DynamoDBItem | null>(null);
  const [jsonInput, setJsonInput] = useState('');
  const [jsonError, setJsonError] = useState('');

  const { data: itemsResponse, isLoading } = useTableItems(tableName, tenantId);
  const putItemMutation = usePutItem();
  const deleteItemMutation = useDeleteItem();

  const items = itemsResponse?.items || [];

  const partitionKey = table.key_schema.find((k) => k.KeyType === 'HASH')?.AttributeName || '';
  const sortKey = table.key_schema.find((k) => k.KeyType === 'RANGE')?.AttributeName;

  const handleCreateClick = () => {
    setEditingItem(null);
    setJsonInput('{\n  \n}');
    setJsonError('');
    setIsCreateModalOpen(true);
  };

  const handleEditClick = (item: DynamoDBItem) => {
    setEditingItem(item);
    setJsonInput(JSON.stringify(item, null, 2));
    setJsonError('');
    setIsCreateModalOpen(true);
  };

  const handleSaveItem = async () => {
    try {
      const parsed = JSON.parse(jsonInput);

      await putItemMutation.mutateAsync({
        tableName,
        tenantId,
        item: parsed,
      });

      setIsCreateModalOpen(false);
      setEditingItem(null);
      setJsonInput('');
    } catch (error) {
      if (error instanceof SyntaxError) {
        setJsonError('Invalid JSON: ' + error.message);
      } else {
        setJsonError((error as Error).message);
      }
    }
  };

  const handleDeleteItem = async (item: DynamoDBItem) => {
    if (!confirm('Are you sure you want to delete this item?')) return;

    const key: Record<string, any> = {};
    key[partitionKey] = item[partitionKey];
    if (sortKey) {
      key[sortKey] = item[sortKey];
    }

    try {
      await deleteItemMutation.mutateAsync({
        tableName,
        tenantId,
        key,
      });
    } catch (error) {
      alert('Failed to delete item: ' + (error as Error).message);
    }
  };

  const getDisplayValue = (value: any): string => {
    if (value === null || value === undefined) return '-';
    if (typeof value === 'object') return JSON.stringify(value);
    return String(value);
  };

  const getKeyValue = (item: DynamoDBItem): string => {
    const parts = [partitionKey + '=' + getDisplayValue(item[partitionKey])];
    if (sortKey) {
      parts.push(sortKey + '=' + getDisplayValue(item[sortKey]));
    }
    return parts.join(', ');
  };

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="text-gray-600">Loading items...</div>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <p className="text-sm text-gray-600">
          {items.length} {items.length === 1 ? 'item' : 'items'}
        </p>
        <Button variant="primary" onClick={handleCreateClick}>
          Create item
        </Button>
      </div>

      {items.length === 0 ? (
        <div className="rounded-lg border border-gray-200 bg-white p-8 text-center">
          <h3 className="mb-2 text-lg font-medium text-gray-900">No items</h3>
          <p className="mb-4 text-gray-600">Create your first item to get started</p>
          <Button variant="primary" onClick={handleCreateClick}>
            Create item
          </Button>
        </div>
      ) : (
        <div className="rounded-lg border border-gray-200 bg-white">
          <table className="w-full">
            <thead className="border-b border-gray-200 bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-600">
                  Key
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-600">
                  Attributes
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-600">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {items.map((item, index) => (
                <tr key={index} className="hover:bg-gray-50">
                  <td className="px-6 py-4 text-sm font-medium text-gray-900">
                    {getKeyValue(item)}
                  </td>
                  <td className="px-6 py-4">
                    <div className="max-w-2xl overflow-hidden text-ellipsis text-sm text-gray-600">
                      {JSON.stringify(item)}
                    </div>
                  </td>
                  <td className="px-6 py-4 text-right">
                    <div className="flex justify-end gap-2">
                      <Button
                        variant="secondary"
                        onClick={() => handleEditClick(item)}
                      >
                        Edit
                      </Button>
                      <Button
                        variant="secondary"
                        onClick={() => handleDeleteItem(item)}
                        disabled={deleteItemMutation.isPending}
                      >
                        Delete
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Modal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        title={editingItem ? 'Edit item' : 'Create item'}
      >
        <div className="space-y-4">
          <div>
            <label htmlFor="jsonInput" className="block text-sm font-medium text-gray-700">
              Item data (JSON format)
            </label>
            <textarea
              id="jsonInput"
              value={jsonInput}
              onChange={(e) => {
                setJsonInput(e.target.value);
                setJsonError('');
              }}
              rows={15}
              className={`mt-1 w-full rounded border px-3 py-2 font-mono text-sm focus:outline-none ${
                jsonError
                  ? 'border-red-500 focus:border-red-500'
                  : 'border-gray-300 focus:border-blue-500'
              }`}
              placeholder='{\n  "id": {"S": "123"},\n  "name": {"S": "Example"}\n}'
            />
            {jsonError && <p className="mt-1 text-sm text-red-600">{jsonError}</p>}
            <p className="mt-1 text-xs text-gray-600">
              Use DynamoDB JSON format: {'{'}"{partitionKey}": {'{'}"{table.attribute_definitions.find(a => a.AttributeName === partitionKey)?.AttributeType || 'S'}": "value"{'}'}...{'}'}
            </p>
          </div>

          <div className="flex justify-end gap-3">
            <Button
              variant="secondary"
              onClick={() => setIsCreateModalOpen(false)}
            >
              Cancel
            </Button>
            <Button
              variant="primary"
              onClick={handleSaveItem}
              disabled={putItemMutation.isPending}
            >
              {putItemMutation.isPending
                ? 'Saving...'
                : editingItem
                ? 'Save changes'
                : 'Create item'}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
