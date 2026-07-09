import { format, formatDistanceToNow } from "date-fns";
import { Loader2 } from "lucide-react";
import React from "react";
import { PiCoinsDuotone, PiClockCountdownDuotone } from "react-icons/pi";

import type { TokenUsage as TokenUsageData } from "@/api/tokens";
import { useGetTokenUsageQuery } from "@/store/apiSlice";


// import RecentTransactionsAccordion from "./RecentTransactionsAccordion";

/* -------------------- Utils -------------------- */

const formatDateTime = (value: string | null) => {
  if (!value) return "—";

  return format(new Date(value), "MMM d, yyyy · h:mm a");
};

const formatLabel = (value: string) =>
  value.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());

const usagePercent = (used: number, limit: number) => {
  if (limit <= 0) return 0;

  return Math.min(100, Math.round((used / limit) * 100));
};

/* -------------------- UI Pieces -------------------- */

const CircularProgress = ({
  percent,
  label,
  subLabel,
  colorClass,
  badgeText,
  badgeColorClass,
  description,
}: {
  percent: number;
  label: string;
  subLabel: string;
  colorClass: string;
  badgeText: string;
  badgeColorClass: string;
  description: string;
}) => {
  const size = 120;
  const strokeWidth = 8;
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  const strokeDashoffset = circumference - (percent / 100) * circumference;

  return (
    <div className="flex flex-col sm:flex-row items-center gap-5 p-5 rounded-2xl border border-border bg-card/50 backdrop-blur-sm hover:shadow-md transition-all duration-300">
      <div className="relative shrink-0" style={{ width: size, height: size }}>
        <svg className="w-full h-full transform -rotate-90">
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            className="text-secondary/50 dark:text-secondary/20"
            strokeWidth={strokeWidth}
            stroke="currentColor"
            fill="transparent"
          />
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            className={`${colorClass} transition-all duration-1000 ease-out`}
            strokeWidth={strokeWidth}
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
            stroke="currentColor"
            fill="transparent"
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-xl font-bold tracking-tight text-foreground">{percent}%</span>
          <span className="text-[9px] font-semibold text-muted-foreground uppercase tracking-wider">{subLabel}</span>
        </div>
      </div>

      <div className="flex-1 text-center sm:text-left space-y-2">
        <div className="flex flex-wrap items-center gap-2 justify-center sm:justify-start">
          <h4 className="font-semibold text-sm text-foreground">{label}</h4>
          <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider border ${badgeColorClass}`}>
            {badgeText}
          </span>
        </div>
        <p className="text-xs text-muted-foreground leading-relaxed">
          {description}
        </p>
      </div>
    </div>
  );
};

const getDailyStatus = (percent: number) => {
  if (percent < 50) {
    return {
      colorClass: "text-green-500",
      badgeText: "Optimal",
      badgeColorClass: "bg-green-500/10 text-green-600 dark:text-green-400 border-green-500/20",
    };
  } else if (percent < 85) {
    return {
      colorClass: "text-indigo-500",
      badgeText: "Moderate",
      badgeColorClass: "bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border-indigo-500/20",
    };
  } else {
    return {
      colorClass: "text-red-500",
      badgeText: percent >= 100 ? "Limit Reached" : "Warning",
      badgeColorClass: "bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/20",
    };
  }
};

const getWalletStatus = (percent: number) => {
  if (percent >= 60) {
    return {
      colorClass: "text-green-500",
      badgeText: "Excellent Pool",
      badgeColorClass: "bg-green-500/10 text-green-600 dark:text-green-400 border-green-500/20",
    };
  } else if (percent >= 25) {
    return {
      colorClass: "text-indigo-500",
      badgeText: "Adequate Pool",
      badgeColorClass: "bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border-indigo-500/20",
    };
  } else {
    return {
      colorClass: "text-red-500",
      badgeText: percent <= 0 ? "Empty" : "Critical Low",
      badgeColorClass: "bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/20",
    };
  }
};

const RefillCard = ({ usage }: { usage: TokenUsageData }) => (
  <div className="rounded-2xl border border-primary/20 bg-gradient-to-br from-primary/5 to-secondary/5 p-6 space-y-6">
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-xl bg-primary/10 text-primary">
          <PiClockCountdownDuotone size={20} />
        </div>
        <div>
          <h3 className="font-semibold text-sm">Refill & Tier Schedule</h3>
          <p className="text-xs text-muted-foreground text-left">Keep track of your high-speed allocations</p>
        </div>
      </div>
      <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-gradient-to-r from-primary to-violet-600 text-white shadow-sm">
        {usage.tier_name || "Foundation"}
      </span>
    </div>

    <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 pt-4 border-t border-border/50">
      <div>
        <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest mb-1">
          Next Refill
        </p>
        <p className="font-bold text-sm text-foreground">
          {formatDateTime(usage.next_refill_at)}
        </p>
        {usage.next_refill_at && (
          <p className="text-xs text-muted-foreground mt-0.5">
            {formatDistanceToNow(new Date(usage.next_refill_at), {
              addSuffix: true,
            })}
          </p>
        )}
      </div>

      <div>
        <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest mb-1">
          Last Refill
        </p>
        <p className="font-semibold text-sm text-foreground">
          {formatDateTime(usage.last_refill_at)}
        </p>
      </div>

      <div>
        <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest mb-1">
          Refill Frequency
        </p>
        <p className="font-semibold text-sm text-foreground">
          {formatLabel(usage.refill_frequency)}
        </p>
      </div>
    </div>
  </div>
);

const UsageDetails = ({ usage }: { usage: TokenUsageData }) => {
  const dailyPercent = usagePercent(usage.daily_tokens_used, usage.daily_token_limit);
  const walletPercent = usagePercent(usage.available_tokens, usage.weekly_tokens);

  const dailyStatus = getDailyStatus(dailyPercent);
  const walletStatus = getWalletStatus(walletPercent);

  return (
    <div className="space-y-4 px-1">
      <h3 className="text-sm font-semibold text-left">Usage & Limits</h3>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <CircularProgress
          percent={dailyPercent}
          label="Daily Request Limit"
          subLabel="Used"
          colorClass={dailyStatus.colorClass}
          badgeText={dailyStatus.badgeText}
          badgeColorClass={dailyStatus.badgeColorClass}
          description="Your daily messaging capacity. This resets automatically every 24 hours to give you a fresh pool of reasoning power."
        />

        <CircularProgress
          percent={walletPercent}
          label="Remaining Wallet Pool"
          subLabel="Available"
          colorClass={walletStatus.colorClass}
          badgeText={walletStatus.badgeText}
          badgeColorClass={walletStatus.badgeColorClass}
          description="Your premium allocation pool. High-speed reasoning queries are deducted from this pool and refilled periodically based on your tier."
        />
      </div>
    </div>
  );
};

const LoadingState = () => (
  <div className="flex justify-center py-12">
    <Loader2 className="h-8 w-8 animate-spin text-primary" />
  </div>
);

const ErrorState = ({ message }: { message: string }) => (
  <p className="text-sm text-red-500 bg-red-500/10 p-4 rounded-lg border border-red-500/20">
    {message}
  </p>
);

/* -------------------- Main Component -------------------- */

interface TokenUsageProps {
  embedded?: boolean;
}

const TokenUsage: React.FC<TokenUsageProps> = ({ embedded = false }) => {
  const {
    data: usage,
    isLoading: isUsageLoading,
    isError: isUsageError,
    error: usageError,
  } = useGetTokenUsageQuery();

  // const {
  //   data: transactionsData,
  //   isLoading: isTransactionsLoading,
  // } = useGetTokenTransactionsQuery({ limit: 10, offset: 0 });

  const usageErrorMessage =
    usageError && "status" in usageError
      ? "Unable to load token usage. Make sure you have an active subscription."
      : "Unable to load token usage.";

  const content = (
    <>
      {isUsageLoading && <LoadingState />}
      {isUsageError && !isUsageLoading && (
        <ErrorState message={usageErrorMessage} />
      )}
      {usage && !isUsageLoading && (
        <div className="space-y-6">
          <UsageDetails usage={usage} />
          <RefillCard usage={usage} />

          {/* ---------------- Transaction History (This is just for testing purpose will remove it later) --------------- */}
          {/* <RecentTransactionsAccordion
            transactions={transactionsData?.items ?? []}
            isLoading={isTransactionsLoading}
          /> */}
        </div>
      )}
    </>
  );

  if (embedded) {
    return <div>{content}</div>;
  }

  return (
    <section className="bg-card border border-border p-6 rounded-2xl neon-card">
      <h2 className="text-xl font-semibold mb-6 flex items-center gap-2">
        <PiCoinsDuotone size={22} className="text-primary" />
        Token Usage
      </h2>
      {content}
    </section>
  );
};

export default TokenUsage;
