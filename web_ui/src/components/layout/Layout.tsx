import { ReactNode } from 'react';
import { Navbar } from './Navbar';

interface LayoutProps {
  children: ReactNode;
}

export function Layout({ children }: LayoutProps) {
  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      <main>{children}</main>
      <footer className="bg-white border-t border-gray-200 mt-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center justify-between">
            <div className="text-sm text-gray-500">
              MiniStack Console v1.0.0 | MIT Licensed | Free Forever
            </div>
            <div className="flex space-x-6">
              <a
                href="https://github.com/ministackorg/ministack"
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-gray-500 hover:text-gray-700"
              >
                MiniStack on GitHub
              </a>
              <a
                href="https://github.com/ministackorg/ministack_console"
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-gray-500 hover:text-gray-700"
              >
                Console on GitHub
              </a>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
