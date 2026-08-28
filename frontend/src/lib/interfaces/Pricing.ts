export interface PricingTier {
  level: number;
  name: string;
  description: string;
  highlights: string[];
  is_popular?: boolean;
}
