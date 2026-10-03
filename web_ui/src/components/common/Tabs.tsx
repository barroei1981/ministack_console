import { useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';

export interface Tab {
  id: string;
  label: string;
  content: React.ReactNode;
}

export interface TabsProps {
  tabs: Tab[];
  defaultTab?: string;
}

export function Tabs({ tabs, defaultTab }: TabsProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const activeTabId = searchParams.get('tab') || defaultTab || tabs[0]?.id || '';

  useEffect(() => {
    // Set default tab in URL if not present
    if (!searchParams.get('tab') && (defaultTab || tabs[0]?.id)) {
      const newParams = new URLSearchParams(searchParams);
      newParams.set('tab', defaultTab || tabs[0]?.id || '');
      setSearchParams(newParams, { replace: true });
    }
  }, [defaultTab, tabs, searchParams, setSearchParams]);

  const handleTabChange = (tabId: string) => {
    const newParams = new URLSearchParams(searchParams);
    newParams.set('tab', tabId);
    setSearchParams(newParams);
  };

  const activeTab = tabs.find((tab) => tab.id === activeTabId) || tabs[0];

  return (
    <div className="w-full">
      <div className="border-b border-gray-200">
        <nav className="flex space-x-8" aria-label="Tabs">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => handleTabChange(tab.id)}
              className={`
                py-4 px-1 border-b-2 font-medium text-sm transition-colors
                ${
                  tab.id === activeTabId
                    ? 'border-aws-orange text-aws-orange'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }
              `}
              aria-current={tab.id === activeTabId ? 'page' : undefined}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>
      <div className="py-6">{activeTab?.content}</div>
    </div>
  );
}
