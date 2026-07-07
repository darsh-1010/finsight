import client from "./client";

export interface PortfolioAsset {
  ticker: string;
  weight: number;
}

export interface CrisisResult {
  return_pct: number;
  max_drawdown: number;
  status: string;
}

export interface StressTestResponse {
  crises: {
    [crisisName: string]: CrisisResult;
  };
}

export const portfolioApi = {
  runStressTest: async (portfolio: PortfolioAsset[]): Promise<StressTestResponse> => {
    const response = await client.post("/portfolio/stress-test", { portfolio });
    return response.data;
  },
};
