import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { useTranslation } from 'react-i18next';
import { Modal } from '../../common/Modal';
import { Button } from '../../common/Button';
import { useCreateBucket } from '../../../hooks/useS3';

const bucketSchema = z.object({
  name: z
    .string()
    .min(3, 'Minimum 3 characters')
    .max(63, 'Maximum 63 characters')
    .regex(/^[a-z0-9][a-z0-9\-\.]*[a-z0-9]$/, 'Lowercase alphanumeric with hyphens/periods')
    .refine((name) => !name.includes('..'), 'No consecutive periods'),
  project: z.string().optional(),
  versioning: z.boolean().default(false),
});

type BucketFormData = z.infer<typeof bucketSchema>;

interface BucketCreateProps {
  isOpen: boolean;
  onClose: () => void;
  tenantId: string;
}

export function BucketCreate({ isOpen, onClose, tenantId }: BucketCreateProps) {
  const { t } = useTranslation();
  const createBucket = useCreateBucket();

  const {
    register,
    handleSubmit,
    formState: { errors, isValid },
    reset,
  } = useForm<BucketFormData>({
    mode: 'onChange',
    defaultValues: {
      name: '',
      project: '',
      versioning: false,
    },
  });

  const onSubmit = async (data: BucketFormData) => {
    try {
      await createBucket.mutateAsync({
        name: data.name,
        tenant_id: tenantId,
        project: data.project || undefined,
        versioning: data.versioning,
      });
      reset();
      onClose();
    } catch (error) {
      // Error handling is done in the mutation hook
    }
  };

  const handleClose = () => {
    reset();
    onClose();
  };

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title={t('s3.create.title')}>
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div>
          <label htmlFor="name" className="block text-sm font-medium text-gray-700 mb-1">
            {t('s3.create.name')}
          </label>
          <input
            id="name"
            type="text"
            {...register('name', {
              validate: (value) => {
                try {
                  bucketSchema.shape.name.parse(value);
                  return true;
                } catch (error) {
                  if (error instanceof z.ZodError) {
                    return error.errors[0]?.message || 'Invalid bucket name';
                  }
                  return 'Invalid bucket name';
                }
              },
            })}
            placeholder={t('s3.create.namePlaceholder')}
            className="w-full px-3 py-2 border border-aws-border rounded-md focus:outline-none focus:ring-2 focus:ring-aws-orange focus:border-transparent"
          />
          {errors.name && (
            <p className="mt-1 text-sm text-red-600">{errors.name.message}</p>
          )}
        </div>

        <div>
          <label htmlFor="project" className="block text-sm font-medium text-gray-700 mb-1">
            {t('s3.create.project')}
          </label>
          <input
            id="project"
            type="text"
            {...register('project')}
            placeholder={t('s3.create.projectPlaceholder')}
            className="w-full px-3 py-2 border border-aws-border rounded-md focus:outline-none focus:ring-2 focus:ring-aws-orange focus:border-transparent"
          />
        </div>

        <div className="flex items-center">
          <input
            id="versioning"
            type="checkbox"
            {...register('versioning')}
            className="h-4 w-4 text-aws-orange focus:ring-aws-orange border-gray-300 rounded"
          />
          <label htmlFor="versioning" className="ml-2 block text-sm text-gray-900">
            {t('s3.create.versioning')}
          </label>
        </div>

        <div className="flex justify-end gap-3 mt-6">
          <Button variant="secondary" onClick={handleClose} type="button">
            {t('s3.create.cancel')}
          </Button>
          <Button
            variant="primary"
            type="submit"
            disabled={!isValid || createBucket.isPending}
            loading={createBucket.isPending}
          >
            {t('s3.create.submit')}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
