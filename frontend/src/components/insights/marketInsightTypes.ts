export type WeeklyTrend = 'Bullish' | 'Bearish' | 'Neutral';
export type TrendType = 'daily' | 'weekly';
export type InsightStatus = 'draft' | 'approved' | 'published' | 'archived';

export interface MarketInsight {
  id: string;
  summary: string;
  source: string;
  tier_required: number;
  
  ticker?: string;
  trend_type?: TrendType;
  trend?: WeeklyTrend;
  price_change_pct?: number;
  key_event?: string;
  verification_status?: string;
  citations?: string[];
  alert_message?: string;
  status: InsightStatus;
  
  published_at?: string;
  expires_at?: string;
  created_at: string;
}
