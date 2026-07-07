import type React from 'react';

import type { InsightResponse } from '@/store/apiSlice';

const InsightMeta: React.FC<{ insight: InsightResponse }> = ({ insight }) => (
  <div className="mt-3 flex flex-wrap gap-2 text-xs text-muted-foreground">
    {insight.ticker && (
      <span className="rounded-md bg-secondary px-2 py-1 font-semibold text-foreground">
        {insight.ticker}
      </span>
    )}
    <span className="rounded-md bg-secondary px-2 py-1">
      Tier {insight.tier_required}
    </span>
    {insight.trend_type && (
      <span className="rounded-md bg-secondary px-2 py-1 capitalize">
        {insight.trend_type}
      </span>
    )}
    {typeof insight.price_change_pct === 'number' && (
      <span className="rounded-md bg-secondary px-2 py-1">
        {insight.price_change_pct.toFixed(2)}%
      </span>
    )}
  </div>
);

export default InsightMeta;
