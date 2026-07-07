import { Loader2, CheckCircle2, AlertCircle } from 'lucide-react';
import React, { useEffect, useState } from 'react';

import { adminApi, type ScrapingURLResponse } from '@/api/admin';
import { useWebSocket } from '@/hooks/useWebSocket';

type HandleUpdate = (
  id: number,
  field: 'frequency_for_scrapping' | 'content_deletion',
  value:  'DAILY' | 'WEEKLY' | 'MONTHLY',
) => Promise<void>;

/* Logical part */

const fetchUrls = async (
  setUrls: React.Dispatch<React.SetStateAction<ScrapingURLResponse[]>>,
  setLoading: React.Dispatch<React.SetStateAction<boolean>>,
  setError: React.Dispatch<React.SetStateAction<string | null>>,
) => {
  try {
    setLoading(true);
    const data = await adminApi.listScrapingURLs();

    setUrls(data);
  } catch (err) {
    setError('Failed to fetch scraping URLs.');
    console.error(err);
  } finally {
    setLoading(false);
  }
};

const updateUrlsFromSocket = (
  lastMessage: string | null,
  setUrls: React.Dispatch<React.SetStateAction<ScrapingURLResponse[]>>,
) => {
  if (!lastMessage) return;

  try {
    const parsed = JSON.parse(lastMessage);

    if (parsed.type !== 'SCRAPING_STATUS' || !Array.isArray(parsed.data))
      return;

    setUrls((prev) => prev.map((url) => {
      const updated = parsed.data.find(
        (d: ScrapingURLResponse) => d.id === url.id,
      );

      return updated
        ? { ...url, status: updated.status, job_id: updated.job_id }
        : url;
    }),
    );
  } catch {
    // Ignore non-JSON messages
  }
};

const updateScrapingSetting = async ({
  id,
  field,
  value,
  setUpdatingId,
  setError,
  setSuccess,
  setUrls,
}: {
  id: number;
  field: 'frequency_for_scrapping' | 'content_deletion';
  value: 'HOURLY' | 'DAILY' | 'WEEKLY' | 'MONTHLY';
  setUpdatingId: React.Dispatch<React.SetStateAction<number | null>>;
  setError: React.Dispatch<React.SetStateAction<string | null>>;
  setSuccess: React.Dispatch<React.SetStateAction<string | null>>;
  setUrls: React.Dispatch<React.SetStateAction<ScrapingURLResponse[]>>;
}) => {
  try {
    setUpdatingId(id);
    setError(null);
    setSuccess(null);

    await adminApi.updateScrapingURLSettings(id, { [field]: value });

    setUrls((prev) => prev.map((u) => (u.id === id ? { ...u, [field]: value } : u)),
    );

    setSuccess('Setting updated successfully!');
    setTimeout(() => setSuccess(null), 3000);
  } catch (err) {
    setError('Failed to update setting.');
    console.error(err);
  } finally {
    setUpdatingId(null);
  }
};

const useFrequencySetting = () => {
  const [urls, setUrls] = useState<ScrapingURLResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [updatingId, setUpdatingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const { lastMessage } = useWebSocket('/ws');

  useEffect(() => {
    fetchUrls(setUrls, setLoading, setError);
  }, []);

  useEffect(() => {
    updateUrlsFromSocket(lastMessage, setUrls);
  }, [lastMessage]);

  const handleUpdate = (
    id: number,
    field: 'frequency_for_scrapping' | 'content_deletion',
    value: 'DAILY' | 'WEEKLY' | 'MONTHLY',
  ) => updateScrapingSetting({
    id,
    field,
    value,
    setUpdatingId,
    setError,
    setSuccess,
    setUrls,
  });

  return { loading, error, handleUpdate, urls, success, updatingId };
};

/* Static part */

const LoadingComponent = () => (
  <div className="flex flex-col items-center justify-center py-20 animate-in fade-in duration-500">
    <Loader2 className="animate-spin text-primary mb-4" size={40} />
    <p className="text-muted-foreground font-medium">Loading schedules...</p>
  </div>
);

const ErrorComponent = ({ error }: { error: string }) => (
  <div className="mb-6 p-4 bg-red-500/5 border border-red-500/10 text-red-500 rounded-xl flex items-center gap-3 text-sm animate-in fade-in zoom-in-95">
    <AlertCircle size={18} />
    {error}
  </div>
);
const SuccessComponent = ({ success }: { success: string }) => (
  <div className="mb-6 p-4 bg-rose-500/5 border border-rose-500/10 text-rose-500 rounded-xl flex items-center gap-3 text-sm animate-in fade-in zoom-in-95">
    <CheckCircle2 size={18} />
    {success}
  </div>
);

const TableHeadingComponent = () => (
  <thead className="sticky top-0 bg-white dark:bg-gray-900 z-10">
    <tr className="border-b border-gray-200 dark:border-gray-800">
      <th className="py-4 px-4 font-semibold text-sm">Source / URL</th>
      <th className="py-4 px-4 font-semibold text-sm">Scraping Frequency</th>
      <th className="py-4 px-4 font-semibold text-sm">Content Deletion</th>
      <th className="py-4 px-4 font-semibold text-sm">Status</th>
    </tr>
  </thead>
);

const statusDisplayComponent = (url: ScrapingURLResponse) => {
  const statusStr = url.status?.toLowerCase();
  let displayStatus = 'inactive';

  if (['queued', 'started', 'in_progress'].includes(statusStr || '')) {
    displayStatus = 'running';
  } else if (statusStr === 'completed') {
    displayStatus = 'completed';
  } else if (statusStr === 'failed') {
    displayStatus = 'failed';
  }

  switch (displayStatus) {
  case 'completed':
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-medium bg-rose-100 text-rose-800 dark:bg-rose-900/30 dark:text-rose-400 border border-rose-200/50 dark:border-rose-800/50">
        <CheckCircle2 className="w-2.5 h-2.5" />
          Completed
      </span>
    );
  case 'running':
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-medium bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400 border border-blue-200/50 dark:border-blue-800/50">
        <Loader2 className="w-2.5 h-2.5 animate-spin" />
          Running
      </span>
    );
  case 'failed':
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-medium bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400 border border-red-200/50 dark:border-red-800/50">
        <AlertCircle className="w-2.5 h-2.5" />
          Failed
      </span>
    );
  default:
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-medium bg-gray-100 text-gray-800 dark:bg-gray-800/50 dark:text-gray-400 border border-gray-200/50 dark:border-gray-700/50">
        <span className="w-1 h-1 rounded-full bg-gray-400" />
          Inactive
      </span>
    );
  }
};

const SelectComponent = ({
  useFor,
  handleUpdate,
  url,
  updatingId,
}: {
  useFor: 'frequency_for_scrapping' | 'content_deletion';
  handleUpdate: HandleUpdate;
  url: ScrapingURLResponse;
  updatingId: number | null;
}) => (
  <select
    value={url[useFor]}
    onChange={(e) => handleUpdate(
      url.id,
      useFor,
        e.target.value as  'DAILY' | 'WEEKLY' | 'MONTHLY',
    )
    }
    disabled={updatingId === url.id}
    className="bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg px-2 py-1 text-xs focus:ring-2 focus:ring-primary/20 outline-none transition-all cursor-pointer disabled:opacity-50"
  >
    <option value="DAILY">Daily</option>
    <option value="WEEKLY">Weekly</option>
    <option value="MONTHLY">Monthly</option>
  </select>
);

const TableRowComponent = ({
  url,
  handleUpdate,
  updatingId,
}: {
  url: ScrapingURLResponse;
  handleUpdate: HandleUpdate;
  updatingId: number | null;
}) => (
  <tr className="group hover:bg-gray-50/50 dark:hover:bg-gray-800/30 transition-colors">
    <td className="py-4 px-4">
      <div className="flex flex-col">
        <span className="font-medium text-sm text-gray-900 dark:text-gray-100">
          {url.name}
        </span>
        <span
          className="text-xs text-muted-foreground truncate max-w-50"
          title={url.url}
        >
          {url.url}
        </span>
      </div>
    </td>

    <td className="py-4 px-4">
      <SelectComponent
        useFor="frequency_for_scrapping"
        handleUpdate={handleUpdate}
        url={url}
        updatingId={updatingId}
      />
    </td>

    <td className="py-4 px-4">
      <SelectComponent
        useFor="content_deletion"
        handleUpdate={handleUpdate}
        url={url}
        updatingId={updatingId}
      />
    </td>

    <td className="py-4 px-4">{statusDisplayComponent(url)}</td>
  </tr>
);

const TableComponent = ({
  urls,
  handleUpdate,
  updatingId,
}: {
  urls: ScrapingURLResponse[];
  handleUpdate: HandleUpdate;
  updatingId: number | null;
}) => (
  <div className="overflow-x-auto">
    <div className="max-h-110 overflow-y-auto">
      <table className="w-full text-left border-collapse min-w-200">
        <TableHeadingComponent />
        <tbody className="divide-y divide-gray-100 dark:divide-gray-800/50">
          {urls.length === 0 ? (
            <tr>
              <td
                colSpan={3}
                className="py-12 text-center text-muted-foreground"
              >
                No scraping URLs found. Add some in the &quot;Ingest Data&quot;
                tab.
              </td>
            </tr>
          ) : (
            urls.map((url) => (
              <TableRowComponent
                key={url.id}
                url={url}
                handleUpdate={handleUpdate}
                updatingId={updatingId}
              />
            ))
          )}
        </tbody>
      </table>
    </div>
  </div>
);

const FrequencySetting = () => {
  const { loading, error, handleUpdate, urls, success, updatingId } =
    useFrequencySetting();

  if (loading) {
    return <LoadingComponent />;
  }

  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="bg-white/40 dark:bg-gray-900/40 backdrop-blur-2xl border border-gray-200 dark:border-gray-800 rounded-3xl p-8 shadow-xl overflow-hidden">
        {error && <ErrorComponent error={error} />}

        {success && <SuccessComponent success={success} />}
        <TableComponent
          urls={urls}
          handleUpdate={handleUpdate}
          updatingId={updatingId}
        />
      </div>
    </div>
  );
};

export default FrequencySetting;
