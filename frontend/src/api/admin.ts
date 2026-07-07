import client from './client';

export interface ScrapeResponse {
  message: string;
  file_url?: string;
  ml_result: unknown;
}

export interface ScrapingURLResponse {
  id: number;
  name: string;
  url: string;
  frequency_for_scrapping: 'HOURLY' | 'DAILY' | 'WEEKLY' | 'MONTHLY';
  content_deletion: 'HOURLY' | 'DAILY' | 'WEEKLY' | 'MONTHLY';
  status?: string;
  job_id?: string;
}

export interface ScrapingURLUpdate {
  frequency_for_scrapping?: 'HOURLY' | 'DAILY' | 'WEEKLY' | 'MONTHLY';
  content_deletion?: 'HOURLY' | 'DAILY' | 'WEEKLY' | 'MONTHLY';
}

export interface IngestedPDFMetadata {
  id: string;
  name: string;
  url: string;
}

export const adminApi = {
  uploadPDF: async (file: File): Promise<ScrapeResponse> => {
    const formData = new FormData();

    formData.append('file', file);

    const response = await client.post('/admin/scraping/upload-pdf', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });

    return response.data;
  },

  scrapeURL: async (url: string): Promise<ScrapeResponse> => {
    const response = await client.post('/admin/scraping/ingest-scrape-url', { url });

    return response.data;
  },

  listScrapingURLs: async (): Promise<ScrapingURLResponse[]> => {
    const response = await client.get('/admin/scraping/urls');

    return response.data;
  },

  updateScrapingURLSettings: async (
    urlId: number,
    data: ScrapingURLUpdate,
  ): Promise<ScrapingURLResponse> => {
    const response = await client.put(`/admin/scraping/url/${urlId}`, data);

    return response.data;
  },

  getIngestedPDFs: async (): Promise<IngestedPDFMetadata[]> => {
    const response = await client.get('/admin/scraping/ingested-pdf');

    return response.data;
  },

  deleteIngestedPDF: async (pdfId: string): Promise<{ message: string }> => {
    const response = await client.delete(`/admin/scraping/ingested-pdf/${pdfId}`);

    return response.data;
  },
};
