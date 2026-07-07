import client from './client';

export interface TokenUsage {
  user_id: number;
  tier_level: number;
  tier_name: string;
  available_tokens: number;
  total_used_tokens: number;
  daily_tokens_used: number;
  daily_token_limit: number;
  weekly_tokens: number;
  monthly_token_limit: number | null;
  max_tokens_per_prompt: number;
  refill_frequency: string;
  last_refill_at: string | null;
  next_refill_at: string | null;
  usage_date: string;
}

export interface TokenTransaction {
  id: number;
  transaction_type: string;
  tokens: number;
  balance_before: number;
  balance_after: number;
  reference_type: string | null;
  reference_id: number | null;
  description: string | null;
  created_at: string;
}

export interface TokenTransactionList {
  items: TokenTransaction[];
  limit: number;
  offset: number;
}

export const tokensApi = {
  getUsage: async (): Promise<TokenUsage> => {
    const response = await client.get('/tokens/usage');

    return response.data;
  },

  getTransactions: async (limit = 10, offset = 0): Promise<TokenTransactionList> => {
    const response = await client.get('/tokens/transactions', {
      params: { limit, offset },
    });

    return response.data;
  },
};
