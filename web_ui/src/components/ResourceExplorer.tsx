import { useState, useMemo, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useResourceSearch } from '../hooks/useResourceSearch';
import type { SearchResource } from '../types/search';

const SERVICE_TYPE_OPTIONS = [
  { value: '', label: 'All Services' },
  { value: 's3', label: 'S3' },
  { value: 'lambda', label: 'Lambda' },
  { value: 'dynamodb', label: 'DynamoDB' },
];

const RECENT_RESOURCES_KEY = 'ministack_recent_resources';
const MAX_RECENT = 20;

interface RecentResource {
  id: string;
  name: string;
  type: string;
  tenant_id: string;
  accessed_at: string;
  [key: string]: unknown;
}

function getRecentResources(): RecentResource[] {
  try {
    const stored = localStorage.getItem(RECENT_RESOURCES_KEY);
    return stored ? JSON.parse(stored) : [];
  } catch {
    return [];
  }
}

function addRecentResource(resource: SearchResource) {
  const recent = getRecentResources();
  const newRecent: RecentResource = {
    id: resource.id,
    name: resource.name,
    type: resource.type,
    tenant_id: resource.tenant_id,
    accessed_at: new Date().toISOString(),
  };

  // Remove if already exists
  const filtered = recent.filter(r => r.id !== resource.id);

  // Add to front
  const updated = [newRecent, ...filtered].slice(0, MAX_RECENT);

  localStorage.setItem(RECENT_RESOURCES_KEY, JSON.stringify(updated));
}

function getResourcePath(resource: SearchResource): string {
  const type = resource.type;
  const tenantParam = `?tenant_id=${resource.tenant_id}`;

  if (type === 's3:bucket') {
    return `/s3/buckets/${resource.name}${tenantParam}`;
  } else if (type === 'lambda:function') {
    return `/lambda/functions${tenantParam}`;
  } else if (type === 'dynamodb:table') {
    return `/dynamodb/tables/${resource.name}${tenantParam}`;
  }

  return '#';
}

function formatServiceType(type: string): string {
  if (type.startsWith('s3:')) return 'S3';
  if (type.startsWith('lambda:')) return 'Lambda';
  if (type.startsWith('dynamodb:')) return 'DynamoDB';
  return type;
}

export function ResourceExplorer() {
  const tenantId = useMemo(() => {
    const params = new URLSearchParams(window.location.search);
    return params.get('tenant_id');
  }, []);

  const [searchQuery, setSearchQuery] = useState('');
  const [serviceType, setServiceType] = useState('');
  const [project, setProject] = useState('');
  const [recentResources, setRecentResources] = useState<RecentResource[]>([]);

  const { data: searchResults, isLoading, error } = useResourceSearch({
    query: searchQuery,
    filters: {
      tenant_id: tenantId || undefined,
      service_type: serviceType || undefined,
      project: project || undefined,
    },
    enabled: searchQuery.length > 0,
  });

  useEffect(() => {
    setRecentResources(getRecentResources());
  }, []);

  const handleResourceClick = (resource: SearchResource) => {
    addRecentResource(resource);
    setRecentResources(getRecentResources());
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Resource Explorer</h1>
          <p className="mt-2 text-sm text-gray-600">
            Search across all MiniStack resources
          </p>
        </div>

        {/* Search Bar */}
        <div className="bg-white shadow rounded-lg p-6 mb-6">
          <div className="space-y-4">
            <div>
              <label htmlFor="search" className="block text-sm font-medium text-gray-700 mb-2">
                Search
              </label>
              <input
                id="search"
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search by name or ID..."
                className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
              />
            </div>

            {/* Filters */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label htmlFor="service-type" className="block text-sm font-medium text-gray-700 mb-2">
                  Service Type
                </label>
                <select
                  id="service-type"
                  value={serviceType}
                  onChange={(e) => setServiceType(e.target.value)}
                  className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                >
                  {SERVICE_TYPE_OPTIONS.map(opt => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              </div>

              <div>
                <label htmlFor="project" className="block text-sm font-medium text-gray-700 mb-2">
                  Project
                </label>
                <input
                  id="project"
                  type="text"
                  value={project}
                  onChange={(e) => setProject(e.target.value)}
                  placeholder="Filter by project..."
                  className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                />
              </div>

              <div>
                <label htmlFor="tenant" className="block text-sm font-medium text-gray-700 mb-2">
                  Tenant
                </label>
                <input
                  id="tenant"
                  type="text"
                  value={tenantId || ''}
                  disabled
                  className="w-full px-4 py-2 border border-gray-300 rounded-md bg-gray-50 text-gray-500"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Search Results */}
        {searchQuery.length > 0 && (
          <div className="bg-white shadow rounded-lg mb-6">
            <div className="px-6 py-4 border-b border-gray-200">
              <h2 className="text-lg font-semibold text-gray-900">
                {isLoading ? 'Searching...' : `Search Results (${searchResults?.count || 0})`}
              </h2>
            </div>

            {error && (
              <div className="px-6 py-4">
                <p className="text-red-600">Error: {error instanceof Error ? error.message : 'Search failed'}</p>
              </div>
            )}

            {!isLoading && !error && searchResults && searchResults.results.length === 0 && (
              <div className="px-6 py-8 text-center">
                <p className="text-gray-500">No resources found matching "{searchQuery}"</p>
              </div>
            )}

            {!isLoading && !error && searchResults && searchResults.results.length > 0 && (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Name
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Type
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        ID
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Project
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Actions
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {searchResults.results.map((resource) => (
                      <tr key={resource.id} className="hover:bg-gray-50">
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                          {resource.name}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                            {formatServiceType(resource.type)}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 font-mono">
                          {resource.id}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {resource.project || '-'}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm">
                          <Link
                            to={getResourcePath(resource)}
                            onClick={() => handleResourceClick(resource)}
                            className="text-blue-600 hover:text-blue-900 font-medium"
                          >
                            View Details →
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* Recent Resources */}
        {recentResources.length > 0 && (
          <div className="bg-white shadow rounded-lg">
            <div className="px-6 py-4 border-b border-gray-200">
              <h2 className="text-lg font-semibold text-gray-900">Recently Viewed</h2>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Name
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Type
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Accessed
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {recentResources.map((resource) => (
                    <tr key={resource.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                        {resource.name}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                          {formatServiceType(resource.type)}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {new Date(resource.accessed_at).toLocaleString()}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm">
                        <Link
                          to={getResourcePath(resource)}
                          className="text-blue-600 hover:text-blue-900 font-medium"
                        >
                          View Details →
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Empty State */}
        {searchQuery.length === 0 && recentResources.length === 0 && (
          <div className="bg-white shadow rounded-lg p-12 text-center">
            <svg
              className="mx-auto h-12 w-12 text-gray-400"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
              />
            </svg>
            <h3 className="mt-2 text-sm font-medium text-gray-900">Start searching</h3>
            <p className="mt-1 text-sm text-gray-500">
              Enter a search query to find resources across all services
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
