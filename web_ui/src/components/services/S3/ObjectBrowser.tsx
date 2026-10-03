import { useState, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  useS3Objects,
  useUploadObject,
  useDeleteObjects,
  useDownloadObject,
} from '../../../hooks/useS3Objects';
import { useSSE } from '../../../hooks/useSSE';
import { Breadcrumbs } from '../../common/Breadcrumbs';
import { Button } from '../../common/Button';
import { Table } from '../../common/Table';
import { Modal } from '../../common/Modal';

interface ObjectBrowserProps {
  bucketName: string;
  tenantId: string;
}

type BrowserItem = {
  key: string;
  size?: number;
  last_modified?: string;
  storage_class?: string;
  isFolder: boolean;
};

export default function ObjectBrowser({ bucketName, tenantId }: ObjectBrowserProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const prefix = searchParams.get('prefix') || '';

  const { data, isLoading } = useS3Objects(bucketName, tenantId, prefix);
  const uploadMutation = useUploadObject(bucketName);
  const downloadMutation = useDownloadObject(bucketName);
  const deleteMutation = useDeleteObjects(bucketName);

  // SSE for real-time updates
  useSSE(tenantId);

  const [selectedKeys, setSelectedKeys] = useState<string[]>([]);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<Record<string, number>>({});
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Navigate to a folder
  const navigateToPrefix = (newPrefix: string) => {
    setSearchParams({ prefix: newPrefix });
    setSelectedKeys([]);
  };

  // Build breadcrumb items from current prefix
  const breadcrumbItems = [
    { label: bucketName, onClick: () => navigateToPrefix('') },
  ];

  if (prefix) {
    const parts = prefix.split('/').filter(Boolean);
    parts.forEach((part, index) => {
      const prefixPath = parts.slice(0, index + 1).join('/') + '/';
      breadcrumbItems.push({
        label: part,
        onClick: () => navigateToPrefix(prefixPath),
      });
    });
  }

  // Merge folders and objects into single list
  const items: BrowserItem[] = [
    ...(data?.folders || []).map((folder) => ({
      key: folder.key,
      isFolder: true,
    })),
    ...(data?.objects || []).map((obj) => ({
      key: obj.key,
      size: obj.size,
      last_modified: obj.last_modified,
      storage_class: obj.storage_class,
      isFolder: false,
    })),
  ];

  // Format file size
  const formatSize = (bytes: number | undefined) => {
    if (bytes === undefined) return '-';
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
  };

  // Format date
  const formatDate = (isoString: string | undefined) => {
    if (!isoString) return '-';
    return new Date(isoString).toLocaleString();
  };

  // Get display name (remove prefix)
  const getDisplayName = (key: string) => {
    const withoutPrefix = key.substring(prefix.length);
    // For folders, remove trailing slash
    return withoutPrefix.endsWith('/')
      ? withoutPrefix.slice(0, -1)
      : withoutPrefix;
  };

  // Handle file selection
  const handleFileSelect = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files || files.length === 0) return;

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      if (!file) continue;

      const key = prefix + file.name;

      setUploadProgress((prev) => ({ ...prev, [file.name]: 0 }));

      await uploadMutation.mutateAsync({
        key,
        file,
        tenant_id: tenantId,
        onProgress: (progressEvent: any) => {
          const percentCompleted = Math.round(
            (progressEvent.loaded * 100) / progressEvent.total
          );
          setUploadProgress((prev) => ({ ...prev, [file.name]: percentCompleted }));
        },
      });

      setUploadProgress((prev) => {
        const newProgress = { ...prev };
        delete newProgress[file.name];
        return newProgress;
      });
    }

    // Reset input
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  // Handle delete
  const handleDelete = async () => {
    await deleteMutation.mutateAsync({
      keys: selectedKeys,
      tenant_id: tenantId,
    });
    setSelectedKeys([]);
    setDeleteModalOpen(false);
  };

  // Handle row click
  const handleRowClick = (item: BrowserItem) => {
    if (item.isFolder) {
      navigateToPrefix(item.key);
    }
  };

  // Handle selection
  const toggleSelection = (key: string) => {
    setSelectedKeys((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]
    );
  };

  return (
    <div className="space-y-4">
      {/* Breadcrumbs */}
      <Breadcrumbs items={breadcrumbItems} />

      {/* Actions */}
      <div className="flex items-center gap-3">
        <Button
          onClick={() => fileInputRef.current?.click()}
          disabled={uploadMutation.isPending}
        >
          ⬆️ Upload
        </Button>

        <Button
          onClick={() => downloadMutation.mutate({
            key: selectedKeys[0] || '',
            tenant_id: tenantId
          })}
          disabled={selectedKeys.length !== 1 || selectedKeys.some(k => k.endsWith('/'))}
          variant="secondary"
        >
          ⬇️ Download
        </Button>

        <Button
          onClick={() => setDeleteModalOpen(true)}
          disabled={selectedKeys.length === 0}
          variant="secondary"
        >
          🗑️ Delete
        </Button>

        <input
          ref={fileInputRef}
          type="file"
          multiple
          onChange={handleFileSelect}
          className="hidden"
        />
      </div>

      {/* Upload Progress */}
      {Object.keys(uploadProgress).length > 0 && (
        <div className="space-y-2">
          {Object.entries(uploadProgress).map(([filename, progress]) => (
            <div key={filename} className="flex items-center gap-3">
              <span className="text-sm text-gray-600 dark:text-gray-400 flex-shrink-0">
                {filename}
              </span>
              <div className="flex-1 bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                <div
                  className="bg-blue-600 h-2 rounded-full transition-all"
                  style={{ width: `${progress}%` }}
                />
              </div>
              <span className="text-sm text-gray-600 dark:text-gray-400 flex-shrink-0">
                {progress}%
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Object Table */}
      {isLoading ? (
        <div className="flex justify-center items-center py-12">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-aws-orange"></div>
        </div>
      ) : items.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          {prefix ? 'No objects in this folder' : 'No objects in bucket'}
        </div>
      ) : (
        <div className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
          <Table
            columns={[
            {
              key: 'selection',
              label: '',
              render: (item: BrowserItem) => (
                <input
                  type="checkbox"
                  checked={selectedKeys.includes(item.key)}
                  onChange={() => toggleSelection(item.key)}
                  className="rounded border-gray-300 dark:border-gray-600"
                />
              ),
            },
            {
              key: 'name',
              label: 'Name',
              render: (item: BrowserItem) => (
                <div
                  className="flex items-center gap-2 cursor-pointer hover:text-blue-600"
                  onClick={() => handleRowClick(item)}
                >
                  {item.isFolder ? (
                    <span className="text-2xl">📁</span>
                  ) : (
                    <span className="text-2xl">📄</span>
                  )}
                  <span>{getDisplayName(item.key)}</span>
                </div>
              ),
            },
            {
              key: 'size',
              label: 'Size',
              render: (item: BrowserItem) => formatSize(item.size),
            },
            {
              key: 'last_modified',
              label: 'Last Modified',
              render: (item: BrowserItem) => formatDate(item.last_modified),
            },
            {
              key: 'storage_class',
              label: 'Storage Class',
              render: (item: BrowserItem) => item.storage_class || '-',
            },
          ]}
            data={items}
          />
        </div>
      )}

      {/* Delete Confirmation Modal */}
      <Modal
        isOpen={deleteModalOpen}
        onClose={() => setDeleteModalOpen(false)}
        title="Delete Objects"
      >
        <div className="space-y-4">
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Are you sure you want to delete {selectedKeys.length} object(s)? This action cannot be undone.
          </p>

          <div className="max-h-40 overflow-y-auto space-y-1">
            {selectedKeys.map((key) => (
              <div key={key} className="text-sm text-gray-700 dark:text-gray-300">
                • {getDisplayName(key)}
              </div>
            ))}
          </div>

          <div className="flex gap-3 justify-end">
            <Button
              variant="secondary"
              onClick={() => setDeleteModalOpen(false)}
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
