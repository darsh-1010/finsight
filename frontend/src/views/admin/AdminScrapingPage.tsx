import { FileUp, Clock, History } from 'lucide-react';
import React from 'react';
import { useSearchParams } from 'react-router-dom';

import FrequencySetting from '@/components/admin/scraping/FrequencySetting';
import PDFIngestion from '@/components/admin/scraping/PDFIngestion';
import ScrapingContent from '@/components/admin/scraping/ScrapingContent';
import ScrapingHistory from '@/components/admin/scraping/ScrapingHistory';
import { cn } from '@/lib/utils';

type MainTab = 'ingest' | 'frequency' | 'content' | 'history';

// --- Sub-components ---

const ScrapingHeader: React.FC<{ activeTab: MainTab }> = ({ activeTab }) => {
  const getHeaderContent = () => {
    switch (activeTab) {
    case 'content':
      return {
        title: 'Scraped Insights',
        description:
            'Browse and manage all content ingested from verified sources.',
      };
    case 'ingest':
      return {
        title: 'Data Ingestion',
        description:
            "Expand FinSight's knowledge base by uploading PDFs or scraping URLs.",
      };
    case 'frequency':
      return {
        title: 'Scraping Schedules',
        description:
            'Manage automated scraping frequencies and content deletion policies.',
      };
    case 'history':
      return {
        title: 'Scraping History',
        description:
            'Track the performance and status of recent scraping executions.',
      };
    default:
      return {
        title: 'Data Ingestion & Management',
        description:
            "Expand FinSight's knowledge base or manage scraping schedules.",
      };
    }
  };

  const { title, description } = getHeaderContent();

  return (
    <div className="mb-8">
      <h1 className="text-2xl md:text-3xl font-bold tracking-tight">{title}</h1>
      <p className="text-sm md:text-base text-muted-foreground mt-2">
        {description}
      </p>
    </div>
  );
};

const TabButton: React.FC<{
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
}> = ({ active, onClick, icon, label }) => (
  <button
    onClick={onClick}
    className={cn(
      'flex-1 flex items-center justify-center gap-2 py-3 px-4 text-sm font-medium transition-all rounded-xl border whitespace-nowrap min-w-fit',
      active
        ? 'bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700 shadow-sm text-primary'
        : 'border-transparent text-muted-foreground hover:bg-gray-100 dark:hover:bg-gray-800/50',
    )}
  >
    {icon}
    {label}
  </button>
);

const MainTabSelector: React.FC<{
  activeTab: MainTab;
  setActiveTab: (tab: MainTab) => void;
}> = ({ activeTab, setActiveTab }) => (
  <div className="flex overflow-x-auto bg-gray-100/50 dark:bg-gray-800/50 p-1.5 rounded-2xl mb-8 gap-1.5 max-w-full mx-auto scrollbar-hide">
    <TabButton
      active={activeTab === 'frequency'}
      onClick={() => setActiveTab('frequency')}
      icon={<Clock size={18} />}
      label="Frequency Setting"
    />
    <TabButton
      active={activeTab === 'content'}
      onClick={() => setActiveTab('content')}
      icon={<FileUp size={18} />} // Can use a better icon if preferred, using FileUp for now
      label="Scraping Content"
    />

    <TabButton
      active={activeTab === 'history'}
      onClick={() => setActiveTab('history')}
      icon={<History size={18} />}
      label="Scraping History"
    />
    <TabButton
      active={activeTab === 'ingest'}
      onClick={() => setActiveTab('ingest')}
      icon={<FileUp size={18} />}
      label="Ingest Data"
    />
  </div>
);

const AdminScrapingPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const tabParam = searchParams.get('tab');
  
  const activeTab: MainTab = (tabParam === 'ingest' || tabParam === 'frequency' || tabParam === 'content' || tabParam === 'history')
    ? tabParam
    : 'content';

  const setActiveTab = (tab: MainTab) => {
    setSearchParams({ tab });
  };

  return (
    <div className="max-w-7xl mx-auto p-6 md:p-8">
      <ScrapingHeader activeTab={activeTab} />
      <MainTabSelector activeTab={activeTab} setActiveTab={setActiveTab} />

      {activeTab === 'ingest' && <PDFIngestion />}
      {activeTab === 'frequency' && <FrequencySetting />}
      {activeTab === 'content' && <ScrapingContent />}
      {activeTab === 'history' && <ScrapingHistory />}
    </div>
  );
};

export default AdminScrapingPage;
