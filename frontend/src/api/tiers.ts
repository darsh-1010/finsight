import client from './client';

export interface Tier {
  id: number;
  name: string;
  price_amount: number;
  price_id: string;
  price_amount_yearly?: number;
  yearly_price_id?: string | null;
  description: string;
  level: number;
  highlights: string[];
  is_popular: boolean;
}

export const tiersApi = {
  getTiers: async (): Promise<Tier[]> => {
    const response = await client.get('/tiers');

    if (!Array.isArray(response.data)) {
      throw new Error("Invalid tiers data received. API may be misconfigured.");
    }

    return response.data;
  },
};
