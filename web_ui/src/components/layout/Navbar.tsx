import { Link, useSearchParams } from 'react-router-dom';
import { useState } from 'react';

export function Navbar() {
  const [searchParams, setSearchParams] = useSearchParams();
  const currentTenant = searchParams.get('tenant_id') || '000000000001';
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  const handleTenantChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newTenant = e.target.value;
    setSearchParams({ tenant_id: newTenant });
  };

  return (
    <nav className="bg-gray-900 border-b border-gray-700 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <div className="flex items-center">
            <Link to={`/?tenant_id=${currentTenant}`} className="flex items-center">
              <div className="flex-shrink-0">
                <svg className="h-8 w-8 text-orange-500" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M12 2L2 7v10c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V7l-10-5zm0 18c-3.86-.96-7-5.1-7-9V8.3l7-3.11 7 3.11V11c0 3.9-3.14 8.04-7 9z"/>
                  <path d="M7 10h2v7H7zm4-3h2v10h-2zm4 6h2v4h-2z"/>
                </svg>
              </div>
              <div className="ml-3">
                <div className="text-white text-lg font-bold">MiniStack Console</div>
                <div className="text-gray-400 text-xs">AWS Emulator Control-Plane</div>
              </div>
            </Link>
          </div>

          {/* Desktop Navigation */}
          <div className="hidden md:flex items-center space-x-4">
            <Link
              to={`/?tenant_id=${currentTenant}`}
              className="text-gray-300 hover:text-white px-3 py-2 rounded-md text-sm font-medium"
            >
              Services
            </Link>
            <Link
              to={`/explorer?tenant_id=${currentTenant}`}
              className="text-gray-300 hover:text-white px-3 py-2 rounded-md text-sm font-medium"
            >
              Search
            </Link>
            <Link
              to={`/graph?tenant_id=${currentTenant}`}
              className="text-gray-300 hover:text-white px-3 py-2 rounded-md text-sm font-medium"
            >
              Graph
            </Link>
            <Link
              to={`/projects?tenant_id=${currentTenant}`}
              className="text-gray-300 hover:text-white px-3 py-2 rounded-md text-sm font-medium"
            >
              Projects
            </Link>

            {/* Tenant Selector */}
            <div className="flex items-center border-l border-gray-700 pl-4">
              <label htmlFor="tenant" className="text-gray-400 text-sm mr-2">
                Tenant:
              </label>
              <select
                id="tenant"
                value={currentTenant}
                onChange={handleTenantChange}
                className="bg-gray-800 text-white text-sm rounded px-3 py-1 border border-gray-700 focus:outline-none focus:border-orange-500"
              >
                <option value="000000000001">000000000001 (Default)</option>
                <option value="123456789012">123456789012</option>
                <option value="999999999999">999999999999</option>
              </select>
            </div>
          </div>

          {/* Mobile menu button */}
          <div className="md:hidden">
            <button
              onClick={() => setIsMenuOpen(!isMenuOpen)}
              className="text-gray-400 hover:text-white focus:outline-none"
            >
              <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                {isMenuOpen ? (
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                ) : (
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                )}
              </svg>
            </button>
          </div>
        </div>

        {/* Mobile menu */}
        {isMenuOpen && (
          <div className="md:hidden pb-4">
            <div className="space-y-1">
              <Link
                to={`/?tenant_id=${currentTenant}`}
                className="text-gray-300 hover:text-white block px-3 py-2 rounded-md text-base font-medium"
                onClick={() => setIsMenuOpen(false)}
              >
                Services
              </Link>
              <Link
                to={`/explorer?tenant_id=${currentTenant}`}
                className="text-gray-300 hover:text-white block px-3 py-2 rounded-md text-base font-medium"
                onClick={() => setIsMenuOpen(false)}
              >
                Search
              </Link>
              <Link
                to={`/graph?tenant_id=${currentTenant}`}
                className="text-gray-300 hover:text-white block px-3 py-2 rounded-md text-base font-medium"
                onClick={() => setIsMenuOpen(false)}
              >
                Graph
              </Link>
              <Link
                to={`/projects?tenant_id=${currentTenant}`}
                className="text-gray-300 hover:text-white block px-3 py-2 rounded-md text-base font-medium"
                onClick={() => setIsMenuOpen(false)}
              >
                Projects
              </Link>

              <div className="pt-4 border-t border-gray-700">
                <label htmlFor="tenant-mobile" className="text-gray-400 text-sm px-3 block mb-2">
                  Tenant:
                </label>
                <select
                  id="tenant-mobile"
                  value={currentTenant}
                  onChange={handleTenantChange}
                  className="mx-3 bg-gray-800 text-white text-sm rounded px-3 py-2 border border-gray-700 w-[calc(100%-1.5rem)]"
                >
                  <option value="000000000001">000000000001 (Default)</option>
                  <option value="123456789012">123456789012</option>
                  <option value="999999999999">999999999999</option>
                </select>
              </div>
            </div>
          </div>
        )}
      </div>
    </nav>
  );
}
