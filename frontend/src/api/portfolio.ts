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

export interface StressScenario {
  id: string;
  name: string;
  category: string;
  description: string;
  type: "historical" | "synthetic";
  start_date?: string;
  end_date?: string;
}

export const portfolioApi = {
  runStressTest: async (
    portfolio: PortfolioAsset[],
    scenarios?: string[]
  ): Promise<StressTestResponse> => {
    const response = await client.post("/portfolio/stress-test", {
      portfolio,
      scenarios,
    });
    return response.data;
  },

  getStressScenarios: async (): Promise<StressScenario[]> => {
    const response = await client.get("/portfolio/stress-test/scenarios");
    return response.data;
  },
};
