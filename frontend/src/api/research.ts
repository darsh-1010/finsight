import client from './client';

export interface ResearchSource {
  source: string;
  source_type: string;
  ticker?: string | null;
  data_type: string;
  url?: string | null;
  id?: string | null;
  retrieved_at?: string | null;
  confidence: number;
}

export interface ResearchReport {
  ticker: string;
  company_name?: string | null;
  generated_at: string;
  summary: string;
  valuation_take: string;
  growth_take: string;
  risk_take: string;
  filing_highlights: string[];
  sources: ResearchSource[];
  confidence: number;
  warnings: string[];
  from_cache: boolean;
}

export const researchApi = {
  getReport: async (ticker: string): Promise<ResearchReport> => {
    const response = await client.post('/research/report', { ticker });

    return response.data;
  },
};
