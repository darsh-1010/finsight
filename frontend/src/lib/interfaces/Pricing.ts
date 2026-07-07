export interface PricingTier {
  level: number;
  name: string;
  price_amount: string | number;
  price_amount_yearly?: string | number;
  price_id?: string | null;
  yearly_price_id?: string | null;
  description: string;
  highlights: string[];
  is_popular?: boolean;
}
