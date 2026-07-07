// src/config/insights.ts
export const INSIGHTS_ACCESS = [
  {
    entitlement: 'INSIGHTS_BASIC',
    minTier: 2,
    label: 'Basic Market Insights',
    description: 'Educational market explainers and trends',
  },
  {
    entitlement: 'INSIGHTS_PORTFOLIO',
    minTier: 3,
    label: 'Portfolio Insights',
    description: 'Macro context & portfolio-level reasoning',
  },
  {
    entitlement: 'INSIGHTS_PRO',
    minTier: 4,
    label: 'Pro Insights',
    description: 'Signals-aware AI interpretations',
  },
];
