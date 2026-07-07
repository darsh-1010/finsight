import React, { useState, useMemo } from "react";

import AdminInsightsHeader from "@/components/admin/insights/AdminInsightsHeader";
import {
  EmptyState,
  ErrorState,
  LoadingState,
} from "@/components/admin/insights/AdminInsightsStates";
import AdminInsightsFilters, { type TrendType } from "@/components/admin/insights/AdminInsightsFilters";
import InsightCard from "@/components/admin/insights/InsightCard";
import TierTabs from "@/components/admin/insights/TierTabs";
import type {
  InsightStatusChangePayload,
  TierInsightGroup,
} from "@/components/admin/insights/types";
import {
  useGetAdminInsightsQuery,
  useUpdateAdminInsightStatusMutation,
} from "@/store/apiSlice";

const buildTierGroups = (insights: { tier_required: number }[]) => {
  const counts = insights.reduce<Record<number, number>>((acc, insight) => {
    acc[insight.tier_required] = (acc[insight.tier_required] || 0) + 1;
    return acc;
  }, {});

  return Object.entries(counts)
    .map<TierInsightGroup>(([tier, count]) => ({
      tier: Number(tier),
      count,
    }))
    .sort((a, b) => a.tier - b.tier);
};



const AdminInsightsPage: React.FC = () => {
  const {
    data: insights = [],
    isLoading,
    isFetching,
    error,
    refetch,
  } = useGetAdminInsightsQuery();
  const [activeTier, setActiveTier] = useState<number | null>(null);
  const [activeStatus, setActiveStatus] = useState<string>('all');
  const [trendFilter, setTrendFilter] = useState<TrendType>('all');
  
  const [updateStatus, { isLoading: isUpdating }] =
    useUpdateAdminInsightStatusMutation();

  const tierGroups = useMemo(() => buildTierGroups(insights), [insights]);

  React.useEffect(() => {
    if (tierGroups.length === 0) {
      setActiveTier(null);
      return;
    }

    if (!activeTier || !tierGroups.some((group) => group.tier === activeTier)) {
      setActiveTier(tierGroups[0].tier);
    }
  }, [activeTier, tierGroups]);

  React.useEffect(() => {
    if ((activeTier === 1 || activeTier === 2) && trendFilter === 'daily') {
      setTrendFilter('all');
    }
  }, [activeTier, trendFilter, setTrendFilter]);

  const tierFilteredInsights = useMemo(() => {
    return activeTier
      ? insights.filter((insight) => insight.tier_required === activeTier)
      : [];
  }, [activeTier, insights]);

  const filteredInsights = useMemo(() => {
    let result = tierFilteredInsights;
      
    if (activeStatus !== 'all') {
      result = result.filter(i => i.status.toLowerCase() === activeStatus.toLowerCase());
    }
    
    if (trendFilter !== 'all') {
      result = result.filter(i => i.trend_type === trendFilter);
    }
    
    return result;
  }, [tierFilteredInsights, activeStatus, trendFilter]);

  const handleStatusChange = (payload: InsightStatusChangePayload) => {
    void updateStatus(payload);
  };

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-4 md:p-8">
      <AdminInsightsHeader refetch={refetch} isFetching={isFetching} />

      {isLoading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState />
      ) : insights.length === 0 ? (
        <EmptyState />
      ) : (
        <>
          <TierTabs
            groups={tierGroups}
            activeTier={activeTier}
            onTierChange={setActiveTier}
          />
          
          <AdminInsightsFilters
            activeStatus={activeStatus}
            setActiveStatus={setActiveStatus}
            trendFilter={trendFilter}
            setTrendFilter={setTrendFilter}
            tierFilteredInsights={tierFilteredInsights}
            activeTier={activeTier}
          />
          
          <div className="space-y-4" role="tabpanel">
            {filteredInsights.map((insight) => (
              <InsightCard
                key={insight.id}
                insight={insight}
                onStatusChange={handleStatusChange}
                isUpdating={isUpdating}
              />
            ))}
          </div>
          
          <div className="text-center text-xs text-muted-foreground pt-4">
            Showing {filteredInsights.length} insights in Tier {activeTier}
          </div>
        </>
      )}
    </div>
  );
};

export default AdminInsightsPage;
