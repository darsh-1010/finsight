/* eslint-disable max-lines-per-function */
import { Info } from 'lucide-react';
import React, { useState, useEffect } from 'react';

import ActivePipelines from '@/components/admin/dashboard/ActivePipelines';
import DashboardHeader from '@/components/admin/dashboard/DashboardHeader';
import MetricsGrid from '@/components/admin/dashboard/MetricsGrid';
import PendingApprovalQueue from '@/components/admin/dashboard/PendingApprovalQueue';
import ScraperRunLogs from '@/components/admin/dashboard/ScraperRunLogs';
import SyncControlCenter from '@/components/admin/dashboard/SyncControlCenter';
import {
  useGetAdminInsightsQuery,
  useGetScrapingURLsQuery,
  useGetScrapingHistoryQuery,
  useGetScrapingSubURLsQuery,
  useUpdateAdminInsightStatusMutation,
} from '@/store/apiSlice';

const AdminDashboard: React.FC = () => {
  // --- RTK Query Hooks ---
  const {
    data: insights = [],
    isLoading: isInsightsLoading,
    isFetching: isInsightsFetching,
    refetch: refetchInsights,
  } = useGetAdminInsightsQuery();

  const {
    data: scrapingURLs = [],
    isLoading: isScrapingURLsLoading,
    isFetching: isScrapingURLsFetching,
    refetch: refetchScrapingURLs,
  } = useGetScrapingURLsQuery();

  const {
    data: scrapingHistory = [],
    isLoading: isScrapingHistoryLoading,
    isFetching: isScrapingHistoryFetching,
    refetch: refetchScrapingHistory,
  } = useGetScrapingHistoryQuery();

  const {
    data: scrapingSubURLs = [],
    isLoading: isScrapingSubURLsLoading,
    isFetching: isScrapingSubURLsFetching,
    refetch: refetchScrapingSubURLs,
  } = useGetScrapingSubURLsQuery();

  // Combine fetching states
  const isFetchingAll =
    isInsightsFetching ||
    isScrapingURLsFetching ||
    isScrapingHistoryFetching ||
    isScrapingSubURLsFetching;

  // --- Mutations ---
  const [updateStatus, { isLoading: isUpdating }] = useUpdateAdminInsightStatusMutation();

  // --- Local States ---
  const [bannerAlert, setBannerAlert] = useState<{
    message: string;
    type: 'success' | 'error' | 'info';
  } | null>(null);

  // Auto-dismiss alert banner after 6 seconds
  useEffect(() => {
    if (bannerAlert) {
      const timer = setTimeout(() => {
        setBannerAlert(null);
      }, 6000);

      return () => clearTimeout(timer);
    }
  }, [bannerAlert]);

  // --- Computed Stats ---
  const pendingInsights = insights.filter((i) => i.status === 'draft');
  const totalPipelines = scrapingURLs.length;
  const totalArticles = scrapingSubURLs.length;

  // Calculate success rate over the last 30 job history records
  const last30Runs = scrapingHistory.slice(0, 30);
  const completedRuns = last30Runs.filter((r) => r.status?.toLowerCase() === 'completed').length;
  const successRate = last30Runs.length > 0 ? (completedRuns / last30Runs.length) * 100 : 100;

  // --- Event Handlers ---
  const handleRefreshAll = () => {
    void refetchInsights();
    void refetchScrapingURLs();
    void refetchScrapingHistory();
    void refetchScrapingSubURLs();
  };

  const handleShowAlert = (message: string, type: 'success' | 'error' | 'info') => {
    setBannerAlert({ message, type });
  };

  const handleQuickApproval = async (id: string, status: 'approved' | 'rejected') => {
    try {
      await updateStatus({
        entity_id: id,
        status,
        review_notes: `Quick decision from dashboard on ${new Date().toLocaleDateString()}`,
      }).unwrap();
      setBannerAlert({
        message: `Insight status successfully updated to ${status}.`,
        type: 'success',
      });
    } catch (err: unknown) {
      console.error(err);
      setBannerAlert({
        message: 'Failed to update insight status. Please try again.',
        type: 'error',
      });
    }
  };

  return (
    <div className="p-4 md:p-8 max-w-7xl mx-auto space-y-6">
      
      {/* --- Notification Banner --- */}
      {bannerAlert && (
        <div
          className={`flex items-start gap-3 p-4 rounded-xl border backdrop-blur-md transition-all duration-300 animate-in fade-in slide-in-from-top-4 ${
            bannerAlert.type === 'success'
              ? 'bg-rose-500/10 text-rose-500 border-rose-500/20'
              : bannerAlert.type === 'error'
                ? 'bg-rose-500/10 text-rose-500 border-rose-500/20'
                : 'bg-blue-500/10 text-blue-500 border-blue-500/20'
          }`}
        >
          <Info className="w-5 h-5 shrink-0 mt-0.5" />
          <div className="flex-1 text-sm font-medium">
            {bannerAlert.message}
          </div>
          <button
            onClick={() => setBannerAlert(null)}
            className="text-muted-foreground hover:text-foreground text-xs font-bold px-1.5 py-0.5 rounded-md hover:bg-secondary/10"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* --- Dashboard Header --- */}
      <DashboardHeader
        isFetchingAll={isFetchingAll}
        onRefresh={handleRefreshAll}
      />

      {/* --- Metrics Overview Grid --- */}
      <MetricsGrid
        totalPipelines={totalPipelines}
        isScrapingURLsLoading={isScrapingURLsLoading}
        totalArticles={totalArticles}
        isScrapingSubURLsLoading={isScrapingSubURLsLoading}
        pendingReviewCount={pendingInsights.length}
        isInsightsLoading={isInsightsLoading}
        successRate={successRate}
        isScrapingHistoryLoading={isScrapingHistoryLoading}
      />

      {/* --- Main Dashboard Sections --- */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* Left Side: Pending Queue & Active Pipelines */}
        <div className="lg:col-span-2 space-y-6">
          <PendingApprovalQueue
            pendingInsights={pendingInsights}
            isInsightsLoading={isInsightsLoading}
            isUpdating={isUpdating}
            onQuickApproval={handleQuickApproval}
          />
          <ActivePipelines
            scrapingURLs={scrapingURLs}
            isScrapingURLsLoading={isScrapingURLsLoading}
          />
        </div>

        {/* Right Side: Sync Controls & Run Logs */}
        <div className="space-y-6">
          <SyncControlCenter
            onShowAlert={handleShowAlert}
          />
          <ScraperRunLogs
            scrapingHistory={scrapingHistory}
            isScrapingHistoryLoading={isScrapingHistoryLoading}
          />
        </div>

      </div>

    </div>
  );
};

export default AdminDashboard;
