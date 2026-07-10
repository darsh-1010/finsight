import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';

import type { BrokerResponse, BrokerCreate, BrokerUpdate, BrokersUploadResponse } from '@/api/brokers';
import type { TokenTransactionList, TokenUsage } from '@/api/tokens';
import type { ScrapingURLResponse, IngestedPDFMetadata } from '@/api/admin';

export interface ScrapingJobHistory {
  id: number;
  run_id: string;
  job_id: string;
  website_id: number;
  name: string;
  status: string;
  queued_at?: string | null;
  started_at?: string | null;
  in_progress_at?: string | null;
  completed_at?: string | null;
  error?: string | null;
}

export interface ScrapingSubURL {
  id: number;
  scraping_url_id: number;
  source: string;
  url: string;
  title: string;
  summary?: string | null;
  published_date?: string | null;
  scraped_at?: string | null;
  scraper_version?: string | null;
  document_id: string;
}


export interface NotificationResponse {
  id: number;
  title: string;
  message?: string | null;
  notification_type: string;
  entity_type?: string | null;
  entity_id?: string | null;
  priority: 'low' | 'medium' | 'high';
  action_url?: string | null;
  created_by: string;
  created_at: string;
  expires_at?: string | null;
  is_read: boolean;
  audience_types: ('all' | 'tier' | 'user' | 'admin')[];
}

export interface InsightResponse {
  id: string;
  summary?: string | null;
  source?: string | null;
  tier_required: number;
  ticker?: string | null;
  trend_type?: 'daily' | 'weekly' | null;
  trend?: string | null;
  price_change_pct?: number | null;
  key_event?: string | null;
  verification_status?: string | null;
  citations?: string[] | null;
  alert_message?: string | null;
  status: 'draft' | 'approved' | 'rejected' | 'archived';
  published_at?: string | null;
  expires_at?: string | null;
  created_at: string;
}

export interface InsightStatusUpdateRequest {
  entity_id: string;
  status: InsightResponse['status'];
  review_notes?: string | null;
}

const baseQuery = fetchBaseQuery({
  baseUrl: (process.env.NEXT_PUBLIC_API_BASE_URL as string || '')?.replace(/\/+$/, ''),
  credentials: 'include',
  prepareHeaders: (headers) => {
    return headers;
  },
});

// Custom base query with reauth logic
const baseQueryWithReauth: typeof baseQuery = async (args, api, extraOptions) => {
  let result = await baseQuery(args, api, extraOptions);
  
  if (result.error && result.error.status === 401) {
    // Attempt to refresh
    const refreshResult = await baseQuery('/auth/refresh', api, extraOptions);
    
    if (refreshResult.data) {
      // Retry the original query
      result = await baseQuery(args, api, extraOptions);
    } else {
      // Refresh failed, could redirect to login here
    }
  }
  
  return result;
};

export const apiSlice = createApi({
  reducerPath: 'api',
  baseQuery: baseQueryWithReauth,
  tagTypes: ['Broker', 'TokenUsage', 'Notification', 'AdminInsight', 'ScrapingURL', 'ScrapingHistory', 'ScrapingSubURL', 'IngestedPDF'],
  endpoints: (builder) => ({
    getNotifications: builder.query<NotificationResponse[], { limit?: number; unreadOnly?: boolean } | void>({
      query: (arg) => {
        const limit = arg && typeof arg === 'object' && 'limit' in arg ? arg.limit ?? 20 : 20;
        const unreadOnly = arg && typeof arg === 'object' && 'unreadOnly' in arg ? arg.unreadOnly ?? false : false;
        return `/notifications?limit=${limit}&unread_only=${unreadOnly}`;
      },
      providesTags: ['Notification'],
    }),
    markNotificationRead: builder.mutation<{ id: number; notification_id: number; is_read: boolean; read_at: string }, number>({
      query: (id) => ({
        url: `/notifications/${id}/read`,
        method: 'POST',
      }),
      invalidatesTags: ['Notification'],
    }),
    getAdminInsights: builder.query<InsightResponse[], { status?: InsightResponse['status'] } | void>({
      query: (arg) => {
        const status = arg && typeof arg === 'object' && 'status' in arg ? arg.status : undefined;
        const params = status ? `?status=${status}` : '';
        return `/admin/insights${params}`;
      },
      providesTags: ['AdminInsight'],
    }),
    updateAdminInsightStatus: builder.mutation<InsightResponse, InsightStatusUpdateRequest>({
      query: (body) => ({
        url: '/admin/insights/status',
        method: 'POST',
        body,
      }),
      invalidatesTags: ['AdminInsight', 'Notification'],
    }),
    getTokenUsage: builder.query<TokenUsage, void>({
      query: () => '/tokens/usage',
      providesTags: ['TokenUsage'],
    }),
    getTokenTransactions: builder.query<TokenTransactionList, { limit?: number; offset?: number } | void>({
      query: (arg) => {
        const limit = arg && typeof arg === 'object' && 'limit' in arg ? arg.limit ?? 10 : 10;
        const offset = arg && typeof arg === 'object' && 'offset' in arg ? arg.offset ?? 0 : 0;
        return `/tokens/transactions?limit=${limit}&offset=${offset}`;
      },
      providesTags: ['TokenUsage'],
    }),
    getBrokers: builder.query<BrokerResponse[], void>({
      query: () => '/admin/brokers/',
      providesTags: ['Broker'],
    }),
    createBroker: builder.mutation<BrokerResponse, BrokerCreate>({
      query: (data) => ({
        url: '/admin/brokers/',
        method: 'POST',
        body: data,
      }),
      invalidatesTags: ['Broker'],
    }),
    updateBroker: builder.mutation<BrokerResponse, { id: number; data: BrokerUpdate }>({
      query: ({ id, data }) => ({
        url: `/admin/brokers/${id}`,
        method: 'PUT',
        body: data,
      }),
      invalidatesTags: ['Broker'],
    }),
    deleteBroker: builder.mutation<{ message: string }, number>({
      query: (id) => ({
        url: `/admin/brokers/${id}`,
        method: 'DELETE',
      }),
      invalidatesTags: ['Broker'],
    }),
    uploadBrokersCsv: builder.mutation<BrokersUploadResponse, File>({
      query: (file) => {
        const formData = new FormData();
        formData.append('file', file);
        return {
          url: '/admin/brokers/upload',
          method: 'POST',
          body: formData,
        };
      },
      invalidatesTags: ['Broker'],
    }),
    getScrapingURLs: builder.query<ScrapingURLResponse[], void>({
      query: () => '/admin/scraping/urls',
      providesTags: ['ScrapingURL'],
    }),
    getScrapingHistory: builder.query<ScrapingJobHistory[], void>({
      query: () => '/admin/scraping/history',
      providesTags: ['ScrapingHistory'],
    }),
    getScrapingSubURLs: builder.query<ScrapingSubURL[], void>({
      query: () => '/admin/scraping/sub-urls',
      providesTags: ['ScrapingSubURL'],
    }),
    getIngestedPDFs: builder.query<IngestedPDFMetadata[], void>({
      query: () => '/admin/scraping/ingested-pdf',
      providesTags: ['IngestedPDF'],
    }),
    syncInsights: builder.mutation<{ message: string }, { mode: 'daily' | 'weekly' }>({
      query: ({ mode }) => ({
        url: `/admin/insights/sync?mode=${mode}`,
        method: 'POST',
      }),
      invalidatesTags: ['AdminInsight', 'Notification'],
    }),
  }),
});

export const {
  useGetNotificationsQuery,
  useMarkNotificationReadMutation,
  useGetAdminInsightsQuery,
  useUpdateAdminInsightStatusMutation,
  useGetBrokersQuery,
  useGetTokenUsageQuery,
  useGetTokenTransactionsQuery,
  useCreateBrokerMutation,
  useUpdateBrokerMutation,
  useDeleteBrokerMutation,
  useUploadBrokersCsvMutation,
  useGetScrapingURLsQuery,
  useGetScrapingHistoryQuery,
  useGetScrapingSubURLsQuery,
  useGetIngestedPDFsQuery,
  useSyncInsightsMutation,
} = apiSlice;
