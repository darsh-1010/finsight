import { useEffect, useState, useRef } from "react";
import { ChevronLeft, ChevronRight, Sparkles, Archive } from "lucide-react";
import { useSearchParams } from "react-router-dom";

import { contentApi } from "@/api/content";
import type { MarketInsight } from "./marketInsightTypes";
import { useAuth } from "@/context/AuthContext";
import { cn } from "@/lib/utils";

import { isToday, isCurrentWeek } from "./helpers";
import { CarouselCard } from "./CarouselCard";
import { StatsGrid } from "./StatsGrid";
import { ArchiveView } from "./ArchiveView";

const MarketInsightsContent = () => {
  const { user } = useAuth();
  const [insights, setInsights] = useState<MarketInsight[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchParams, setSearchParams] = useSearchParams();
  const [viewMode, setViewMode] = useState<"latest" | "archive">("latest");
  const [carouselIndex, setCarouselIndex] = useState(0);
  const [isHovering, setIsHovering] = useState(false);

  // States for Archive
  const [searchQuery, setSearchQuery] = useState("");
  const [trendFilter, setTrendFilter] = useState("all");
  const [showFilterPanel, setShowFilterPanel] = useState(false);
  const [expandedArchiveSignalId, setExpandedArchiveSignalId] = useState<
    string | null
  >(null);
  const [expandedArchiveDateGroups, setExpandedArchiveDateGroups] = useState<
    Record<string, boolean>
  >({});

  const isTier1Or2 = (user?.tier_level || 0) > 0 && (user?.tier_level || 0) <= 2;
  const requestedTab = searchParams.get("tab");
  const activeTab = isTier1Or2 ? "weekly" : (requestedTab === "weekly" ? "weekly" : "daily");

  const [highlightedSignalId, setHighlightedSignalId] = useState<string | null>(
    null,
  );
  const insightId = searchParams.get("insightId");
  const prevInsightIdRef = useRef<string | null>(null);
  const hasInitialFetchedRef = useRef(false);

  useEffect(() => {
    const shouldFetch =
      !hasInitialFetchedRef.current ||
      (insightId && insightId !== prevInsightIdRef.current);

    if (shouldFetch) {
      const fetchInsights = async () => {
        try {
          setLoading(true);
          const data = await contentApi.fetchInsights();
          setInsights(data);
          hasInitialFetchedRef.current = true;
        } catch (error) {
          console.error("Failed to fetch market insights", error);
        } finally {
          setLoading(false);
        }
      };

      fetchInsights();
    }

    prevInsightIdRef.current = insightId;
  }, [insightId]);

  // Filter based on selected trend type (Daily / Weekly) and matching tier level
  const sortedFilteredInsights = [...insights]
    .filter(
      (insight) =>
        insight.trend_type === activeTab &&
        insight.tier_required === (user?.tier_level || 0),
    )
    .sort((a, b) => {
      const dateA = a.published_at ? new Date(a.published_at).getTime() : 0;
      const dateB = b.published_at ? new Date(b.published_at).getTime() : 0;
      return dateB - dateA;
    });

  // Separate latest vs archived insights
  const isLatestInsight = (insight: MarketInsight) => {
    const dateStr = insight.published_at || insight.created_at;
    if (activeTab === "daily") {
      return isToday(dateStr);
    } else {
      return isCurrentWeek(dateStr);
    }
  };

  const latestInsights = sortedFilteredInsights.filter(isLatestInsight);
  const archiveInsights = sortedFilteredInsights.filter(
    (insight) => !isLatestInsight(insight),
  );

  // Auto-scroll Carousel every 6 seconds unless user interacts
  useEffect(() => {
    setCarouselIndex(0); // Reset on tab/view changes
  }, [activeTab, viewMode]);

  useEffect(() => {
    if (viewMode !== "latest" || latestInsights.length <= 1 || isHovering)
      return;
    const timer = setInterval(() => {
      setCarouselIndex((prev) => (prev + 1) % latestInsights.length);
    }, 20000);
    return () => clearInterval(timer);
  }, [viewMode, latestInsights.length, isHovering]);

  const handleTabChange = (tab: "daily" | "weekly") => {
    setSearchParams({ tab });
  };

  // Stats Counters (reflects the current view's dataset)
  const activeDataset =
    viewMode === "latest" ? latestInsights : archiveInsights;
  const bullishCount = activeDataset.filter(
    (i) => i.trend === "Bullish",
  ).length;
  const bearishCount = activeDataset.filter(
    (i) => i.trend === "Bearish",
  ).length;
  const totalCount = activeDataset.length;

  // Process Archive view data (only Yesterday/Older)
  const archivedFiltered = archiveInsights.filter((insight) => {
    const matchesSearch =
      !searchQuery ||
      insight.ticker?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      false ||
      insight.key_event?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      false ||
      insight.summary?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      false;

    const matchesTrend =
      trendFilter === "all" ||
      insight.trend?.toLowerCase() === trendFilter.toLowerCase();

    return matchesSearch && matchesTrend;
  });

  const groupedByDate: Record<string, MarketInsight[]> = {};
  archivedFiltered.forEach((insight) => {
    const dateStr = insight.published_at || insight.created_at;
    const dateKey = new Date(dateStr).toDateString();
    if (!groupedByDate[dateKey]) {
      groupedByDate[dateKey] = [];
    }
    groupedByDate[dateKey].push(insight);
  });

  const sortedDateKeys = Object.keys(groupedByDate).sort((a, b) => {
    return new Date(b).getTime() - new Date(a).getTime();
  });

  // Default expand the first date group when archive loads
  useEffect(() => {
    if (sortedDateKeys.length > 0) {
      setExpandedArchiveDateGroups((prev) => {
        if (Object.keys(prev).length === 0) {
          return { [sortedDateKeys[0]]: true };
        }
        return prev;
      });
    }
  }, [sortedDateKeys]);

  // Redirect to correct tab and open appropriate card based on URL parameters
  useEffect(() => {
    const targetInsightId = searchParams.get("insightId");
    if (!targetInsightId || insights.length === 0) return;

    const targetInsight = insights.find((i) => i.id === targetInsightId);
    if (!targetInsight) return;

    const targetTab = targetInsight.trend_type || "daily";
    if (activeTab !== targetTab) {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          next.set("tab", targetTab);
          return next;
        },
        { replace: true },
      );
      return;
    }

    setHighlightedSignalId(targetInsightId);

    const filteredForTab = insights
      .filter(
        (insight) =>
          insight.trend_type === targetTab &&
          insight.tier_required === (user?.tier_level || 0),
      )
      .sort((a, b) => {
        const dateA = a.published_at ? new Date(a.published_at).getTime() : 0;
        const dateB = b.published_at ? new Date(b.published_at).getTime() : 0;
        return dateB - dateA;
      });

    const isLatest = isLatestInsight(targetInsight);
    if (isLatest) {
      setViewMode("latest");

      const latestInsightsLocal = filteredForTab.filter(isLatestInsight);
      const idx = latestInsightsLocal.findIndex(
        (i) => i.id === targetInsightId,
      );
      if (idx !== -1) {
        setCarouselIndex(idx);
      }
    } else {
      setViewMode("archive");
      const dateKey = new Date(
        targetInsight.published_at || targetInsight.created_at,
      ).toDateString();
      setExpandedArchiveDateGroups((prev) => ({
        ...prev,
        [dateKey]: true,
      }));
      setExpandedArchiveSignalId(targetInsightId);
    }
  }, [insights, searchParams, activeTab, user?.tier_level]);

  // Scroll to and clear highlight
  useEffect(() => {
    if (!highlightedSignalId) return;

    const scrollTimer = setTimeout(() => {
      const element = document.getElementById(
        `insight-card-${highlightedSignalId}`,
      );
      if (element) {
        element.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    }, 300);

    const clearTimer = setTimeout(() => {
      setHighlightedSignalId(null);
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          next.delete("insightId");
          return next;
        },
        { replace: true },
      );
    }, 4000);

    return () => {
      clearTimeout(scrollTimer);
      clearTimeout(clearTimer);
    };
  }, [highlightedSignalId, setSearchParams]);

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="space-y-4 md:space-y-5">
      {/* Header with Title and Control Toggles */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 border-b border-border/40 pb-4">
        <div className="text-left">
          <h1 className="text-2xl md:text-3xl font-extrabold tracking-tight capitalize text-foreground">
            {activeTab} AI-Assisted Market Signals
          </h1>
          <p className="mt-1.5 max-w-2xl text-xs md:text-sm text-muted-foreground leading-relaxed">
            Trend direction, price movement, verification status, and
            source-backed references in one place.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3 w-full lg:w-auto justify-start sm:justify-between lg:justify-end">
          {/* View Mode Toggle: Latest vs Archive */}
          <div className="flex rounded-xl bg-slate-100 dark:bg-[#120F1D] p-1 border border-slate-200 dark:border-[#5546FF]/30 shadow-[0_0_15px_rgba(85,70,255,0.08)]">
            <button
              onClick={() => setViewMode("latest")}
              className={cn(
                "flex items-center justify-center gap-1.5 px-4 py-1.5 text-xs sm:text-sm font-semibold rounded-lg transition-all cursor-pointer",
                viewMode === "latest"
                  ? "bg-gradient-to-r from-[#6366F1] to-[#5546FF] text-white shadow-[0_0_12px_rgba(99,102,241,0.35)] font-bold"
                  : "text-slate-500 dark:text-muted-foreground hover:text-slate-900 dark:hover:text-foreground hover:bg-slate-200/50 dark:hover:bg-[#1C1830]",
              )}
            >
              <Sparkles className="h-3.5 w-3.5 text-[#FBBF24] shrink-0" />
              <span>Latest</span>
            </button>
            <button
              onClick={() => setViewMode("archive")}
              className={cn(
                "flex items-center justify-center gap-1.5 px-4 py-1.5 text-xs sm:text-sm font-semibold rounded-lg transition-all cursor-pointer",
                viewMode === "archive"
                  ? "bg-gradient-to-r from-[#6366F1] to-[#5546FF] text-white shadow-[0_0_12px_rgba(99,102,241,0.35)] font-bold"
                  : "text-slate-500 dark:text-muted-foreground hover:text-slate-900 dark:hover:text-foreground hover:bg-slate-200/50 dark:hover:bg-[#1C1830]",
              )}
            >
              <Archive className="h-3.5 w-3.5 text-[#A78BFA] shrink-0" />
              <span>Archive</span>
            </button>
          </div>

          {/* Filter Switch Toggle: Daily vs Weekly */}
          {!isTier1Or2 && (
            <div className="flex rounded-xl bg-slate-100 dark:bg-zinc-950 p-1 border border-slate-200 dark:border-zinc-800 shadow-sm">
              <button
                onClick={() => handleTabChange("daily")}
                className={cn(
                  "px-3.5 py-1.5 text-xs sm:text-sm font-semibold rounded-lg transition-all cursor-pointer",
                  activeTab === "daily"
                    ? "bg-white dark:bg-zinc-800 text-slate-900 dark:text-white shadow-sm border border-slate-200/30 dark:border-zinc-700/50 font-bold"
                    : "text-slate-500 dark:text-zinc-400 hover:text-slate-950 dark:hover:text-zinc-100 hover:bg-slate-200/50 dark:hover:bg-zinc-800/40",
                )}
              >
                Daily
              </button>
              <button
                onClick={() => handleTabChange("weekly")}
                className={cn(
                  "px-3.5 py-1.5 text-xs sm:text-sm font-semibold rounded-lg transition-all cursor-pointer",
                  activeTab === "weekly"
                    ? "bg-white dark:bg-zinc-800 text-slate-900 dark:text-white shadow-sm border border-slate-200/30 dark:border-zinc-700/50 font-bold"
                    : "text-slate-500 dark:text-zinc-400 hover:text-slate-950 dark:hover:text-zinc-100 hover:bg-slate-200/50 dark:hover:bg-zinc-800/40",
                )}
              >
                Weekly
              </button>
            </div>
          )}
        </div>
      </div>

      {sortedFilteredInsights.length === 0 ? (
        <div className="flex justify-center p-12 text-muted-foreground border border-dashed border-border rounded-2xl">
          No {activeTab} insights available.
        </div>
      ) : viewMode === "latest" ? (
        /* Latest View - Carousel and More Signals List */
        <div className="space-y-4 md:space-y-5">
          {/* Statistics Grid */}
          <StatsGrid
            bullishCount={bullishCount}
            bearishCount={bearishCount}
            totalCount={totalCount}
            activeTab={activeTab}
          />
          
          {latestInsights.length === 0 ? (
            <div className="flex flex-col items-center justify-center p-12 text-muted-foreground border border-dashed border-border/60 bg-card/10 rounded-3xl min-h-[40vh] shadow-sm">
              <Sparkles className="h-10 w-10 text-muted-foreground/30 mb-4" />
              <h3 className="text-lg font-semibold text-foreground/80 mb-1">No Latest Insights</h3>
              <p className="text-sm text-center max-w-md">There are no new {activeTab} market signals at the moment. Check the Archive for past insights.</p>
            </div>
          ) : (
            <div
              className="relative"
              onMouseEnter={() => setIsHovering(true)}
              onMouseLeave={() => setIsHovering(false)}
            >
              <div className="relative min-h-[70vh] md:min-h-[60vh] lg:min-h-[55vh]">
                {latestInsights.map((insight, idx) => (
                  <CarouselCard
                    key={insight.id}
                    insight={insight}
                    isActive={idx === carouselIndex}
                    isHighlighted={insight.id === highlightedSignalId}
                  />
                ))}
              </div>

              {/* Minimalist Carousel Pagination */}
              {latestInsights.length > 1 && (
                <div className="flex items-center justify-center gap-6 mt-6">
                  <button
                    onClick={() =>
                      setCarouselIndex(
                        (prev) =>
                          (prev - 1 + latestInsights.length) %
                          latestInsights.length,
                      )
                    }
                    className="p-1.5 text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
                    aria-label="Previous insight"
                  >
                    <ChevronLeft className="h-5 w-5" />
                  </button>

                  <div className="flex items-center gap-4">
                    <span className="text-xs font-semibold tabular-nums w-4 text-right">
                      {carouselIndex + 1}
                    </span>
                    <div className="w-24 md:w-32 h-1 bg-secondary rounded-full overflow-hidden relative">
                      <div
                        className="absolute top-0 left-0 h-full bg-[#5546FF] transition-all duration-300 ease-out rounded-full"
                        style={{
                          width: `${100 / latestInsights.length}%`,
                          transform: `translateX(${carouselIndex * 100}%)`,
                        }}
                      />
                    </div>
                    <span className="text-xs font-medium text-muted-foreground tabular-nums w-4">
                      {latestInsights.length}
                    </span>
                  </div>

                  <button
                    onClick={() =>
                      setCarouselIndex(
                        (prev) => (prev + 1) % latestInsights.length,
                      )
                    }
                    className="p-1.5 text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
                    aria-label="Next insight"
                  >
                    <ChevronRight className="h-5 w-5" />
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      ) : (
        /* Archive View - Searchable grouped by dates */
        <ArchiveView
          searchQuery={searchQuery}
          setSearchQuery={setSearchQuery}
          trendFilter={trendFilter}
          setTrendFilter={setTrendFilter}
          showFilterPanel={showFilterPanel}
          setShowFilterPanel={setShowFilterPanel}
          sortedDateKeys={sortedDateKeys}
          groupedByDate={groupedByDate}
          expandedArchiveDateGroups={expandedArchiveDateGroups}
          setExpandedArchiveDateGroups={setExpandedArchiveDateGroups}
          expandedArchiveSignalId={expandedArchiveSignalId}
          setExpandedArchiveSignalId={setExpandedArchiveSignalId}
          highlightedSignalId={highlightedSignalId}
        />
      )}
    </div>
  );
};

export default MarketInsightsContent;
