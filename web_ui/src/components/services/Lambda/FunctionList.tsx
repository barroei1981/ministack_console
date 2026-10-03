import { useState, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useFunctions, useDeleteFunction } from '../../../hooks/useLambda';
import { useSSE } from '../../../hooks/useSSE';
import { Button } from '../../common/Button';
import { Table } from '../../common/Table';
import { Modal } from '../../common/Modal';
import { SearchBar } from '../../common/SearchBar';
import { FunctionCreate } from './FunctionCreate';
import type { LambdaFunction } from '../../../types/lambda';

export function FunctionList() {
  const [searchParams] = useSearchParams();
  const tenantId = searchParams.get('tenant_id');

  const { data, isLoading, error } = useFunctions(tenantId);
  const deleteMutation = useDeleteFunction();

  // SSE for real-time updates
  useSSE(tenantId);

  const [searchQuery, setSearchQuery] = useState('');
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [selectedFunction, setSelectedFunction] = useState<LambdaFunction | null>(null);

  // Filter functions by search query
  const filteredFunctions = useMemo(() => {
    if (!data?.functions) return [];
    if (!searchQuery) return data.functions;

    const query = searchQuery.toLowerCase();
    return data.functions.filter(
      (fn) =>
        fn.name.toLowerCase().includes(query) ||
        fn.runtime.toLowerCase().includes(query) ||
        (fn.project && fn.project.toLowerCase().includes(query))
    );
  }, [data?.functions, searchQuery]);

  // Format date
  const formatDate = (isoString: string) => {
    return new Date(isoString).toLocaleString();
  };

  // Format memory
  const formatMemory = (mb: number) => {
    return `${mb} MB`;
  };

  // Format timeout
  const formatTimeout = (seconds: number) => {
    return `${seconds}s`;
  };

  // Handle delete
  const handleDelete = async () => {
    if (!selectedFunction || !tenantId) return;

    await deleteMutation.mutateAsync({
      name: selectedFunction.name,
      tenant_id: tenantId,
    });

    setDeleteModalOpen(false);
    setSelectedFunction(null);
  };

  if (!tenantId) {
    return (
      <div className="min-h-screen bg-white dark:bg-gray-900">
        <header className="bg-aws-blue text-white px-6 py-4">
          <h1 className="text-2xl font-bold">Lambda</h1>
        </header>
        <div className="p-6">
          <div className="bg-yellow-50 border border-yellow-200 rounded-md p-4">
            <p className="text-yellow-800">
              Missing tenant_id query parameter. Please add ?tenant_id=YOUR_TENANT_ID to the URL.
            </p>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-white dark:bg-gray-900">
        <header className="bg-aws-blue text-white px-6 py-4">
          <h1 className="text-2xl font-bold">Lambda</h1>
        </header>
        <div className="p-6">
          <div className="bg-red-50 border border-red-200 rounded-md p-4">
            <p className="text-red-800">
              {error instanceof Error ? error.message : 'Failed to load functions'}
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-white dark:bg-gray-900">
      <header className="bg-aws-blue text-white px-6 py-4">
        <h1 className="text-2xl font-bold">Lambda</h1>
      </header>

      <div className="p-6">
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white">Functions</h2>
          <Button onClick={() => setIsCreateModalOpen(true)}>
            Create function
          </Button>
        </div>

        <div className="mb-4">
          <SearchBar
            value={searchQuery}
            onChange={setSearchQuery}
            placeholder="Search functions..."
          />
        </div>

        {isLoading ? (
          <div className="flex justify-center items-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-aws-orange"></div>
          </div>
        ) : filteredFunctions.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-gray-500 dark:text-gray-400 mb-4">
              {searchQuery ? 'No functions match your search' : 'No functions found'}
            </p>
            {!searchQuery && (
              <Button onClick={() => setIsCreateModalOpen(true)}>
                Create your first function
              </Button>
            )}
          </div>
        ) : (
          <div className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
            <Table
              columns={[
                {
                  key: 'name',
                  label: 'Function name',
                  render: (func: LambdaFunction) => (
                    <div>
                      <div className="font-medium text-gray-900 dark:text-white">
                        {func.name}
                      </div>
                      {func.project && (
                        <div className="text-sm text-gray-500 dark:text-gray-400">
                          Project: {func.project}
                        </div>
                      )}
                    </div>
                  ),
                },
                {
                  key: 'runtime',
                  label: 'Runtime',
                  render: (func: LambdaFunction) => func.runtime,
                },
                {
                  key: 'last_modified',
                  label: 'Last modified',
                  render: (func: LambdaFunction) => formatDate(func.last_modified),
                },
                {
                  key: 'memory',
                  label: 'Memory',
                  render: (func: LambdaFunction) => formatMemory(func.memory),
                },
                {
                  key: 'timeout',
                  label: 'Timeout',
                  render: (func: LambdaFunction) => formatTimeout(func.timeout),
                },
                {
                  key: 'actions',
                  label: 'Actions',
                  render: (func: LambdaFunction) => (
                    <Button
                      variant="secondary"
                      onClick={() => {
                        setSelectedFunction(func);
                        setDeleteModalOpen(true);
                      }}
                    >
                      Delete
                    </Button>
                  ),
                },
              ]}
              data={filteredFunctions}
            />
          </div>
        )}
      </div>

      {/* Create Function Modal */}
      <FunctionCreate
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        tenantId={tenantId}
      />

      {/* Delete Confirmation Modal */}
      <Modal
        isOpen={deleteModalOpen}
        onClose={() => {
          setDeleteModalOpen(false);
          setSelectedFunction(null);
        }}
        title="Delete function"
      >
        <div className="space-y-4">
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Are you sure you want to delete function <strong>{selectedFunction?.name}</strong>?
            This action cannot be undone.
          </p>

          <div className="flex gap-3 justify-end">
            <Button
              variant="secondary"
              onClick={() => {
                setDeleteModalOpen(false);
                setSelectedFunction(null);
              }}
            >
              Cancel
            </Button>
            <Button
              variant="primary"
              onClick={handleDelete}
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
