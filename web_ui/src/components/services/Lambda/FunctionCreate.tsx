import { useState, useRef } from 'react';
import { useCreateFunction } from '../../../hooks/useLambda';
import { Modal } from '../../common/Modal';
import { Button } from '../../common/Button';
import { LAMBDA_RUNTIMES } from '../../../types/lambda';

interface FunctionCreateProps {
  isOpen: boolean;
  onClose: () => void;
  tenantId: string;
}

export function FunctionCreate({ isOpen, onClose, tenantId }: FunctionCreateProps) {
  const createMutation = useCreateFunction();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [formData, setFormData] = useState({
    name: '',
    runtime: 'python3.11',
    handler: 'index.handler',
    memory: 128,
    timeout: 3,
    project: '',
  });

  const [zipFile, setZipFile] = useState<File | null>(null);
  const [envVars, setEnvVars] = useState<Array<{ key: string; value: string }>>([
    { key: '', value: '' },
  ]);
  const [errors, setErrors] = useState<Record<string, string>>({});

  // Validation
  const validate = () => {
    const newErrors: Record<string, string> = {};

    if (!formData.name) {
      newErrors.name = 'Function name is required';
    } else if (!/^[a-zA-Z0-9-_]+$/.test(formData.name)) {
      newErrors.name = 'Name can only contain alphanumeric, hyphens, and underscores';
    } else if (formData.name.length > 64) {
      newErrors.name = 'Name must be 64 characters or less';
    }

    if (!formData.handler) {
      newErrors.handler = 'Handler is required';
    }

    if (formData.memory < 128 || formData.memory > 10240) {
      newErrors.memory = 'Memory must be between 128 and 10240 MB';
    }

    if (formData.timeout < 1 || formData.timeout > 900) {
      newErrors.timeout = 'Timeout must be between 1 and 900 seconds';
    }

    if (!zipFile) {
      newErrors.zipFile = 'ZIP file is required';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  // Handle file selection
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      if (!file.name.endsWith('.zip')) {
        setErrors({ ...errors, zipFile: 'File must be a ZIP file' });
        return;
      }
      setZipFile(file);
      setErrors({ ...errors, zipFile: '' });
    }
  };

  // Add environment variable row
  const addEnvVar = () => {
    setEnvVars([...envVars, { key: '', value: '' }]);
  };

  // Remove environment variable row
  const removeEnvVar = (index: number) => {
    setEnvVars(envVars.filter((_, i) => i !== index));
  };

  // Update environment variable
  const updateEnvVar = (index: number, field: 'key' | 'value', value: string) => {
    const updated = [...envVars];
    if (updated[index]) {
      updated[index][field] = value;
      setEnvVars(updated);
    }
  };

  // Handle submit
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validate()) return;

    if (!zipFile) {
      setErrors({ ...errors, zipFile: 'ZIP file is required' });
      return;
    }

    try {
      // Read file and convert to base64
      const fileBuffer = await zipFile.arrayBuffer();
      const base64Code = btoa(
        String.fromCharCode(...new Uint8Array(fileBuffer))
      );

      // Build environment variables object (filter out empty keys)
      const environment: Record<string, string> = {};
      envVars.forEach(({ key, value }) => {
        if (key.trim()) {
          environment[key.trim()] = value;
        }
      });

      await createMutation.mutateAsync({
        name: formData.name,
        runtime: formData.runtime,
        handler: formData.handler,
        code: base64Code,
        tenant_id: tenantId,
        project: formData.project || undefined,
        environment: Object.keys(environment).length > 0 ? environment : undefined,
        memory: formData.memory,
        timeout: formData.timeout,
      });

      // Reset form and close
      setFormData({
        name: '',
        runtime: 'python3.11',
        handler: 'index.handler',
        memory: 128,
        timeout: 3,
        project: '',
      });
      setZipFile(null);
      setEnvVars([{ key: '', value: '' }]);
      setErrors({});
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
      onClose();
    } catch (error) {
      // Error handled by mutation onError
      console.error('Create function error:', error);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Create function">
      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Function name */}
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            Function name *
          </label>
          <input
            type="text"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-aws-orange dark:bg-gray-800 dark:border-gray-600 dark:text-white"
            placeholder="my-function"
          />
          {errors.name && (
            <p className="mt-1 text-sm text-red-600">{errors.name}</p>
          )}
        </div>

        {/* Runtime */}
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            Runtime *
          </label>
          <select
            value={formData.runtime}
            onChange={(e) => setFormData({ ...formData, runtime: e.target.value })}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-aws-orange dark:bg-gray-800 dark:border-gray-600 dark:text-white"
          >
            {LAMBDA_RUNTIMES.map((runtime) => (
              <option key={runtime.value} value={runtime.value}>
                {runtime.label}
              </option>
            ))}
          </select>
        </div>

        {/* Handler */}
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            Handler *
          </label>
          <input
            type="text"
            value={formData.handler}
            onChange={(e) => setFormData({ ...formData, handler: e.target.value })}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-aws-orange dark:bg-gray-800 dark:border-gray-600 dark:text-white"
            placeholder="index.handler"
          />
          {errors.handler && (
            <p className="mt-1 text-sm text-red-600">{errors.handler}</p>
          )}
          <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
            Format: filename.function_name (e.g., index.handler)
          </p>
        </div>

        {/* Memory and Timeout */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Memory (MB) *
            </label>
            <input
              type="number"
              value={formData.memory}
              onChange={(e) =>
                setFormData({ ...formData, memory: parseInt(e.target.value) })
              }
              min={128}
              max={10240}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-aws-orange dark:bg-gray-800 dark:border-gray-600 dark:text-white"
            />
            {errors.memory && (
              <p className="mt-1 text-sm text-red-600">{errors.memory}</p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Timeout (seconds) *
            </label>
            <input
              type="number"
              value={formData.timeout}
              onChange={(e) =>
                setFormData({ ...formData, timeout: parseInt(e.target.value) })
              }
              min={1}
              max={900}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-aws-orange dark:bg-gray-800 dark:border-gray-600 dark:text-white"
            />
            {errors.timeout && (
              <p className="mt-1 text-sm text-red-600">{errors.timeout}</p>
            )}
          </div>
        </div>

        {/* Project (optional) */}
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            Project (optional)
          </label>
          <input
            type="text"
            value={formData.project}
            onChange={(e) => setFormData({ ...formData, project: e.target.value })}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-aws-orange dark:bg-gray-800 dark:border-gray-600 dark:text-white"
            placeholder="my-project"
          />
        </div>

        {/* ZIP File Upload */}
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            Function code (ZIP) *
          </label>
          <input
            ref={fileInputRef}
            type="file"
            accept=".zip"
            onChange={handleFileChange}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-aws-orange dark:bg-gray-800 dark:border-gray-600 dark:text-white file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:text-sm file:font-semibold file:bg-aws-blue file:text-white hover:file:bg-blue-600"
          />
          {zipFile && (
            <p className="mt-1 text-sm text-green-600">
              Selected: {zipFile.name} ({(zipFile.size / 1024).toFixed(2)} KB)
            </p>
          )}
          {errors.zipFile && (
            <p className="mt-1 text-sm text-red-600">{errors.zipFile}</p>
          )}
        </div>

        {/* Environment Variables */}
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            Environment variables (optional)
          </label>
          <div className="space-y-2">
            {envVars.map((envVar, index) => (
              <div key={index} className="flex gap-2">
                <input
                  type="text"
                  value={envVar.key}
                  onChange={(e) => updateEnvVar(index, 'key', e.target.value)}
                  placeholder="Key"
                  className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-aws-orange dark:bg-gray-800 dark:border-gray-600 dark:text-white"
                />
                <input
                  type="text"
                  value={envVar.value}
                  onChange={(e) => updateEnvVar(index, 'value', e.target.value)}
                  placeholder="Value"
                  className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-aws-orange dark:bg-gray-800 dark:border-gray-600 dark:text-white"
                />
                {envVars.length > 1 && (
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={() => removeEnvVar(index)}
                  >
                    Remove
                  </Button>
                )}
              </div>
            ))}
          </div>
          <Button
            type="button"
            variant="secondary"
            onClick={addEnvVar}
            className="mt-2"
          >
            Add variable
          </Button>
        </div>

        {/* Submit buttons */}
        <div className="flex gap-3 justify-end pt-4 border-t">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button
            type="submit"
            disabled={createMutation.isPending}
          >
            {createMutation.isPending ? 'Creating...' : 'Create function'}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
