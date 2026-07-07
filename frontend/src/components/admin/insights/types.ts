import type { InsightResponse } from '@/store/apiSlice';

export type InsightStatusChangePayload = {
  entity_id: string;
  status: InsightResponse['status'];
  review_notes?: string | null;
};

export type InsightStatusChangeHandler = (
  payload: InsightStatusChangePayload
) => void;

export type TierInsightGroup = {
  tier: number;
  count: number;
};
