import { useState, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useBucket, useUpdateVersioning } from '../../../hooks/useS3';
import { useSSE } from '../../../hooks/useSSE';
import { Breadcrumbs } from '../../common/Breadcrumbs';
import { Tabs } from '../../common/Tabs';
import { Button } from '../../common/Button';
import { BucketDelete } from './BucketDelete';

export function BucketDetail() {
  const { t } = useTranslation();
  const { name } = useParams<{ name: string }>();
  const navigate = useNavigate();
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [showActions, setShowActions] = useState(false);

  // Get tenant_id from URL query params
  const tenantId = useMemo(() => {
    const params = new URLSearchParams(window.location.search);
    return params.get('tenant_id');
  }, []);

  const { data: bucket, isLoading, error } = useBucket(name, tenantId);
  const updateVersioning = useUpdateVersioning();

  // SSE for real-time updates
  useSSE(tenantId);

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

  if (isLoading) {
    return (
      <div className="min-h-screen bg-white">
        <header className="bg-aws-blue text-white px-6 py-4">
          <h1 className="text-2xl font-bold">{t('s3.title')}</h1>
        </header>
        <div className="flex justify-center items-center py-12">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-aws-orange"></div>
        </div>
      </div>
    );
  }

  if (error || !bucket) {
    return (
      <div className="min-h-screen bg-white">
        <header className="bg-aws-blue text-white px-6 py-4">
          <h1 className="text-2xl font-bold">{t('s3.title')}</h1>
        </header>
        <div className="p-6">
          <div className="bg-red-50 border border-red-200 rounded-md p-4">
            <p className="text-red-800">
              {error instanceof Error ? error.message : t('s3.detail.notFound')}
            </p>
            <button
              onClick={() => navigate(`/s3/buckets?tenant_id=${tenantId}`)}
              className="mt-2 text-aws-blue hover:text-aws-orange transition-colors"
            >
              {t('s3.detail.backToList')}
            </button>
          </div>
        </div>
      </div>
    );
  }

  const breadcrumbItems = [
    { label: t('s3.title'), href: `/s3/buckets?tenant_id=${tenantId}` },
    { label: t('s3.detail.buckets'), href: `/s3/buckets?tenant_id=${tenantId}` },
    { label: bucket.name },
  ];

  const handleVersioningToggle = async (enabled: boolean) => {
    if (!bucket) return;
    await updateVersioning.mutateAsync({
      bucketName: bucket.name,
      enabled,
      tenantId,
    });
  };

  const objectCount = (bucket.state?.object_count as number) || 0;

  const tabs = [
    {
      id: 'overview',
      label: t('s3.detail.tabs.overview'),
      content: (
        <div className="space-y-6">
          <dl className="grid grid-cols-1 gap-x-4 gap-y-6 sm:grid-cols-2">
            <div className="sm:col-span-1">
              <dt className="text-sm font-medium text-gray-500">{t('s3.detail.arn')}</dt>
              <dd className="mt-1 text-sm text-gray-900 font-mono">{bucket.arn}</dd>
            </div>
            <div className="sm:col-span-1">
              <dt className="text-sm font-medium text-gray-500">{t('s3.detail.region')}</dt>
              <dd className="mt-1 text-sm text-gray-900">us-east-1</dd>
            </div>
            <div className="sm:col-span-1">
              <dt className="text-sm font-medium text-gray-500">{t('s3.detail.versioning')}</dt>
              <dd className="mt-1 text-sm text-gray-900">
                {bucket.versioning || 'Disabled'}
              </dd>
            </div>
            <div className="sm:col-span-1">
              <dt className="text-sm font-medium text-gray-500">{t('s3.detail.created')}</dt>
              <dd className="mt-1 text-sm text-gray-900">
                {new Date(bucket.created_at).toLocaleString()}
              </dd>
            </div>
            {bucket.project && (
              <div className="sm:col-span-1">
                <dt className="text-sm font-medium text-gray-500">{t('s3.detail.project')}</dt>
                <dd className="mt-1 text-sm text-gray-900">{bucket.project}</dd>
              </div>
            )}
          </dl>
        </div>
      ),
    },
    {
      id: 'properties',
      label: t('s3.detail.tabs.properties'),
      content: (
        <div className="space-y-6">
          <div className="border border-gray-200 rounded-lg p-4">
            <h3 className="text-sm font-medium text-gray-900 mb-4">
              {t('s3.detail.versioningTitle')}
            </h3>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">
                  {t('s3.detail.versioningDescription')}
                </p>
                <p className="text-xs text-gray-500 mt-1">
                  {t('s3.detail.currentStatus')}: {bucket.versioning || 'Disabled'}
                </p>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={bucket.versioning === 'Enabled'}
                  onChange={(e) => handleVersioningToggle(e.target.checked)}
                  disabled={updateVersioning.isPending}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-aws-orange/20 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-aws-orange"></div>
              </label>
            </div>
          </div>
        </div>
      ),
    },
    {
      id: 'tags',
      label: t('s3.detail.tabs.tags'),
      content: (
        <div className="space-y-6">
          <div className="border border-gray-200 rounded-lg p-4">
            <h3 className="text-sm font-medium text-gray-900 mb-4">
              {t('s3.detail.controlPlaneTags')}
            </h3>
            {Object.keys(bucket.tags || {}).length > 0 ? (
              <dl className="space-y-2">
                {Object.entries(bucket.tags || {}).map(([key, value]) => (
                  <div key={key} className="flex justify-between items-center">
                    <dt className="text-sm font-medium text-gray-500">{key}</dt>
                    <dd className="text-sm text-gray-900">{value}</dd>
                  </div>
                ))}
              </dl>
            ) : (
              <p className="text-sm text-gray-500">{t('s3.detail.noTags')}</p>
            )}
          </div>
          <div className="border border-gray-200 rounded-lg p-4">
            <h3 className="text-sm font-medium text-gray-900 mb-4">
              {t('s3.detail.nativeTags')}
            </h3>
            <p className="text-sm text-gray-500">{t('s3.detail.nativeTagsPlaceholder')}</p>
          </div>
        </div>
      ),
    },
  ];

  return (
    <div className="min-h-screen bg-white">
      <header className="bg-aws-blue text-white px-6 py-4">
        <h1 className="text-2xl font-bold">{t('s3.title')}</h1>
      </header>

      <div className="p-6">
        <Breadcrumbs items={breadcrumbItems} />

        <div className="flex justify-between items-center mb-6">
          <h2 className="text-2xl font-bold text-gray-900">{bucket.name}</h2>
          <div className="relative">
            <Button
              variant="secondary"
              onClick={() => setShowActions(!showActions)}
            >
              {t('s3.detail.actions')}
            </Button>
            {showActions && (
              <>
                <div
                  className="fixed inset-0"
                  onClick={() => setShowActions(false)}
                />
                <div className="absolute right-0 mt-2 w-48 bg-white rounded-md shadow-lg z-10 border border-gray-200">
                  <button
                    onClick={() => {
                      setIsDeleteModalOpen(true);
                      setShowActions(false);
                    }}
                    className="block w-full text-left px-4 py-2 text-sm text-red-600 hover:bg-gray-50"
                  >
                    {t('s3.detail.deleteBucket')}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>

        <Tabs tabs={tabs} defaultTab="overview" />
      </div>

      <BucketDelete
        isOpen={isDeleteModalOpen}
        onClose={() => setIsDeleteModalOpen(false)}
        bucketName={bucket.name}
        tenantId={tenantId}
        objectCount={objectCount}
      />
    </div>
  );
}
