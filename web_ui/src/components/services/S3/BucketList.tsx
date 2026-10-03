import { useState, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { useBuckets } from '../../../hooks/useS3';
import { Button } from '../../common/Button';
import { Table } from '../../common/Table';
import { SearchBar } from '../../common/SearchBar';
import { BucketCreate } from './BucketCreate';
import type { Bucket } from '../../../types/s3';
import type { Column } from '../../common/Table';

export function BucketList() {
  const { t } = useTranslation();
  const [searchQuery, setSearchQuery] = useState('');
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);

  // Get tenant_id from URL query params
  const tenantId = useMemo(() => {
    const params = new URLSearchParams(window.location.search);
    return params.get('tenant_id');
  }, []);

  const { data, isLoading, error } = useBuckets(tenantId);

  // Filter buckets based on search query
  const filteredBuckets = useMemo(() => {
    if (!data?.buckets) return [];
    if (!searchQuery) return data.buckets;

    return data.buckets.filter((bucket) =>
      bucket.name?.toLowerCase().includes(searchQuery.toLowerCase())
    );
  }, [data?.buckets, searchQuery]);

  const columns: Column<Bucket>[] = [
    {
      key: 'name',
      label: t('s3.table.name'),
      sortable: true,
    },
    {
      key: 'arn',
      label: t('s3.table.region'),
      render: (bucket: Bucket) => {
        const match = bucket.arn.match(/arn:aws:s3:::(.+)/);
        return match ? 'us-east-1' : '-';
      },
    },
    {
      key: 'versioning',
      label: t('s3.table.versioning'),
      render: (bucket: Bucket) => bucket.versioning || 'Disabled',
    },
    {
      key: 'tags',
      label: t('s3.table.tags'),
      render: (bucket: Bucket) => {
        const tagCount = Object.keys(bucket.tags || {}).length;
        return tagCount > 0 ? `${tagCount} tag(s)` : '-';
      },
    },
    {
      key: 'created_at',
      label: t('s3.table.created'),
      sortable: true,
      render: (bucket: Bucket) => {
        try {
          return new Date(bucket.created_at).toLocaleString();
        } catch {
          return bucket.created_at;
        }
      },
    },
  ];

  if (!tenantId) {
    return (
      <div className="min-h-screen bg-white">
        <header className="bg-aws-blue text-white px-6 py-4">
          <h1 className="text-2xl font-bold">{t('s3.title')}</h1>
        </header>
        <div className="p-6">
          <div className="bg-yellow-50 border border-yellow-200 rounded-md p-4">
            <p className="text-yellow-800">{t('s3.errors.missingTenantId')}</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-white">
      <header className="bg-aws-blue text-white px-6 py-4">
        <h1 className="text-2xl font-bold">{t('s3.title')}</h1>
      </header>

      <div className="p-6">
        <div className="flex justify-between items-center mb-6">
          <SearchBar value={searchQuery} onChange={setSearchQuery} />
          <Button variant="primary" onClick={() => setIsCreateModalOpen(true)}>
            {t('s3.createBucket')}
          </Button>
        </div>

        {isLoading && (
          <div className="flex justify-center items-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-aws-orange"></div>
          </div>
        )}

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-md p-4">
            <p className="text-red-800">
              {error instanceof Error ? error.message : t('s3.apiErrors.loadFailed')}
            </p>
          </div>
        )}

        {!isLoading && !error && filteredBuckets.length === 0 && (
          <div className="text-center py-12 text-gray-500">
            <p>{t('s3.empty')}</p>
          </div>
        )}

        {!isLoading && !error && filteredBuckets.length > 0 && (
          <Table<Bucket> columns={columns} data={filteredBuckets} />
        )}
      </div>

      <BucketCreate
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        tenantId={tenantId}
      />
    </div>
  );
}
