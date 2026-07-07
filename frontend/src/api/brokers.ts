import client from './client';

export interface BrokerResponse {
  id: number;
  name: string;
  redirect_url: string;
}

export interface BrokerCreate {
  name: string;
  redirect_url: string;
}

export interface BrokerUpdate {
  name?: string;
  redirect_url?: string;
}

export interface BrokersUploadResponse {
  message: string;
  count?: number;
  added_count?: number;
  errors?: string[];
}

export const brokersApi = {
  getBrokers: async (): Promise<BrokerResponse[]> => {
    const response = await client.get('/admin/brokers/');

    return response.data;
  },

  createBroker: async (data: BrokerCreate): Promise<BrokerResponse> => {
    const response = await client.post('/admin/brokers/', data);

    return response.data;
  },

  updateBroker: async (id: number, data: BrokerUpdate): Promise<BrokerResponse> => {
    const response = await client.put(`/admin/brokers/${id}`, data);

    return response.data;
  },

  deleteBroker: async (id: number): Promise<{ message: string }> => {
    const response = await client.delete(`/admin/brokers/${id}`);

    return response.data;
  },

  uploadBrokersCsv: async (file: File): Promise<BrokersUploadResponse> => {
    const formData = new FormData();

    formData.append('file', file);

    const response = await client.post('/admin/brokers/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });

    return response.data;
  },
};
