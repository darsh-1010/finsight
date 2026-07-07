import client from './client';

export interface MarketInsight {
  id: string;
  symbol: string;
  name: string;
  price: string;
  change: string;
  isPositive: boolean;
  score: number;
  recommendation: string;
}

export interface MarketInsightsResponse {
  data: MarketInsight[];
  /** "live" when fetched from TradingView, "fallback" when using static data */
  source: 'live' | 'fallback';
}

export const fetchMarketInsights = async (): Promise<MarketInsightsResponse> => {
  const response = await client.get<MarketInsightsResponse>('/market/insights');
  return response.data;
};
