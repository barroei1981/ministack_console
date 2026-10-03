import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Modal } from '../../common/Modal';
import { Button } from '../../common/Button';
import { useDeleteBucket } from '../../../hooks/useS3';

export interface BucketDeleteProps {
  isOpen: boolean;
  onClose: () => void;
  bucketName: string;
  tenantId: string;
  objectCount?: number;
}

export function BucketDelete({
  isOpen,
  onClose,
  bucketName,
  tenantId,
  objectCount = 0,
}: BucketDeleteProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const deleteBucket = useDeleteBucket();
  const [forceDelete, setForceDelete] = useState(false);

  const handleDelete = async () => {
    try {
      await deleteBucket.mutateAsync({
        bucketName,
        tenantId,
        force: forceDelete,
      });
      onClose();
      navigate(`/s3/buckets?tenant_id=${tenantId}`);
    } catch (error) {
      // Error handling is done in the mutation
      // Modal stays open for retry
    }
  };

  const handleClose = () => {
    setForceDelete(false);
    onClose();
  };

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title={t('s3.delete.title')}>
      <div className="space-y-4">
        <p className="text-gray-700">
          {t('s3.delete.confirmMessage', { bucketName, objectCount })}
        </p>

        {objectCount > 0 && (
          <div className="bg-yellow-50 border border-yellow-200 rounded-md p-4">
            <p className="text-yellow-800 text-sm">
              {t('s3.delete.hasObjectsWarning', { objectCount })}
            </p>
            <label className="flex items-center mt-2">
              <input
                type="checkbox"
                checked={forceDelete}
                onChange={(e) => setForceDelete(e.target.checked)}
                className="h-4 w-4 text-aws-orange focus:ring-aws-orange border-gray-300 rounded"
              />
              <span className="ml-2 text-sm text-gray-700">
                {t('s3.delete.forceDelete')}
              </span>
            </label>
          </div>
        )}

        {deleteBucket.isPending && (
          <div className="flex items-center space-x-2 text-gray-600">
            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-aws-orange"></div>
            <span className="text-sm">
              {forceDelete
                ? t('s3.delete.deletingWithObjects', { objectCount })
                : t('s3.delete.deleting')}
            </span>
          </div>
        )}

        <div className="flex justify-end space-x-3">
          <Button
            variant="secondary"
            onClick={handleClose}
            disabled={deleteBucket.isPending}
          >
            {t('s3.delete.cancel')}
          </Button>
          <Button
            variant="primary"
            onClick={handleDelete}
            disabled={deleteBucket.isPending || (objectCount > 0 && !forceDelete)}
            loading={deleteBucket.isPending}
          >
            {objectCount > 0 && forceDelete
              ? t('s3.delete.forceDeleteButton')
              : t('s3.delete.deleteButton')}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
