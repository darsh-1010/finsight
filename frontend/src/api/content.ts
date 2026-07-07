import client from './client';
import type { MarketInsight } from '../components/insights/marketInsightTypes';

export const contentApi = {
  fetchInsights: async (): Promise<MarketInsight[]> => {
    const response = await client.get('/content/insights');
    return response.data;
  },
};
