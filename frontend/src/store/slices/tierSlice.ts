import { createSlice, createAsyncThunk, type PayloadAction } from '@reduxjs/toolkit';

import { tiersApi, type Tier } from '@/api/tiers';
import fallbackTiersData from '../../data/tiers-fallback.json';

interface TierState {
  tiers: Tier[];
  isLoading: boolean;
  error: string | null;
  isFallback: boolean;
}

const initialState: TierState = {
  tiers: [],
  isLoading: false,
  error: null,
  isFallback: false,
};

// Async thunk for fetching tiers
export const fetchTiers = createAsyncThunk<{ data: Tier[]; isFallback: boolean }, void, { rejectValue: string }>(
  'tiers/fetchTiers',
  async (_, { rejectWithValue }) => {
    try {
      const data = await tiersApi.getTiers();

      return { data, isFallback: false };
    } catch (err: unknown) {
      return handleFetchTiersError(err, rejectWithValue);
    }
  }
);

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const handleFetchTiersError = (err: unknown, rejectWithValue: (value: string) => any) => {
  console.error('Failed to fetch tiers, using fallback:', err);
  if (fallbackTiersData && Array.isArray(fallbackTiersData)) {
    return { data: fallbackTiersData, isFallback: true };
  }
  return rejectWithValue('Failed to load pricing tiers. Please try again later.');
};

const tierSlice = createSlice({
  name: 'tiers',
  initialState,
  reducers: {
    // Optional: Add any synchronous actions here if needed
    clearError: (state) => {
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchTiers.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(fetchTiers.fulfilled, (state, action: PayloadAction<{ data: Tier[]; isFallback: boolean }>) => {
        state.isLoading = false;
        state.tiers = action.payload.data;
        state.isFallback = action.payload.isFallback;
        if (action.payload.isFallback) {
          state.error = 'Unable to connect to service. Showing offline pricing.';
        } else {
          state.error = null;
        }
      })
      .addCase(fetchTiers.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      });
  },
});

// Export actions
export const { clearError } = tierSlice.actions;

// Export selectors
export const selectTiers = (state: { tiers: TierState }) => state.tiers.tiers;
export const selectTiersLoading = (state: { tiers: TierState }) => state.tiers.isLoading;
export const selectTiersError = (state: { tiers: TierState }) => state.tiers.error;
export const selectIsFallback = (state: { tiers: TierState }) => state.tiers.isFallback;
export const selectAllTierState = (state: { tiers: TierState }) => state.tiers;

// Export reducer
export default tierSlice.reducer;
