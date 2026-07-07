import { useState, useEffect } from 'react';

import api from '@/api/client';

export interface ScrapingJobHistory {
  id: number;
  run_id: string;
  job_id: string;
  website_id: number;
  name: string;
  status: string;
  queued_at?: string;
  started_at?: string;
  in_progress_at?: string;
  completed_at?: string;
  error?: string;
}

export const statuses = [
  'All Statuses',
  'Queued',
  'Started',
  'In_Progress',
  'Completed',
  'Failed',
];

const getErrorMessage = (err: unknown): string => {
  const errorObj = err as { message?: string };

  return errorObj.message || 'Failed to fetch history. Please try again later.';
};

const filterScrapingHistory = (
  data: ScrapingJobHistory[],
  searchTerm: string,
  selectedStatus: string,
): ScrapingJobHistory[] => {
  const term = searchTerm.toLowerCase();

  return data.filter((item) => {
    const matchesSearch =
      item.name?.toLowerCase().includes(term) ||
      item.job_id?.toLowerCase().includes(term) ||
      item.run_id?.toLowerCase().includes(term);

    const matchesStatus =
      selectedStatus === 'All Statuses' ||
      item.status === selectedStatus.toLowerCase();

    return matchesSearch && matchesStatus;
  });
};

export const useScrapingHistory = () => {
  const [data, setData] = useState<ScrapingJobHistory[]>([]);
  const [filteredData, setFilteredData] = useState<ScrapingJobHistory[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedStatus, setSelectedStatus] = useState('All Statuses');

  const fetchData = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await api.get('/admin/scraping/history');

      setData(response.data);
      setFilteredData(response.data);
    } catch (err: unknown) {
      setError(getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  useEffect(() => {
    setFilteredData(filterScrapingHistory(data, searchTerm, selectedStatus));
  }, [searchTerm, selectedStatus, data]);

  return {
    data,
    filteredData,
    isLoading,
    error,
    selectedStatus,
    searchTerm,
    setSearchTerm,
    setSelectedStatus,
    fetchData,
  };
};
