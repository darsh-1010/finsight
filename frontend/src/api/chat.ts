/* global RequestInit, Response, TextDecoder */
import client from './client';

export interface ChatMessage {
    id: number;
    role: string;
    content: string;
    created_at: string;
}

export interface ChatSession {
    id: number;
    user_id: number;
    session_id: string; // "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    title: string;
    started_at: string;
    messages: ChatMessage[];
}

export interface CreateSessionRequest {
    title?: string;
    first_message?: string;
    model?: string;
}

// ---------- Attachment types ----------

export interface AttachmentResult {
    id?: string;
    filename: string;
    attached: boolean;
    message: string;
    ml_response?: Record<string, unknown> | null;
}

export interface AttachmentUploadResponse {
    session_id: string;
    results: AttachmentResult[];
}

// ---------- Stream helpers ----------

const getStreamUrl = (sessionId: string) => {
  const baseUrl = (import.meta.env.VITE_API_BASE_URL as string)?.replace(/\/+$/, '');

  return `${baseUrl}/chat/sessions/${sessionId}/messages`;
};

const getStreamFetchOptions = (content: string, model: string, attachment_ids?: string[]) => ({
  method: 'POST',
  headers: { 
    'Content-Type': 'application/json',
    'Accept': 'text/event-stream',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive'
  },
  credentials: 'include' as const,
  body: JSON.stringify({ content, role: 'user', model, attachment_ids }),
});

const handleStreamAuthRetry = async (url: string, options: RequestInit) => {
  try {
    await client.get('/auth/refresh');
  } catch {
    throw new Error('Session expired. Please log in again.');
  }

  return fetch(url, options);
};

const performStreamFetch = async (streamUrl: string, fetchOptions: RequestInit) => {
  let response = await fetch(streamUrl, fetchOptions);

  if (response.status === 401) {
    response = await handleStreamAuthRetry(streamUrl, fetchOptions);
  }

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  return response;
};

const doStreamProcessing = async (response: Response, onChunk: (chunk: string) => void) => {
  const reader = response.body?.getReader();
  const decoder = new TextDecoder();

  if (!reader) return;

  while (true) {
    const { done, value } = await reader.read();

    if (done) break;
    onChunk(decoder.decode(value, { stream: true }));
  }
};

export const chatApi = {
  getSessions: async (): Promise<ChatSession[]> => {
    const response = await client.get('/chat/sessions');

    return response.data;
  },


  getSessionById: async (sessionId: string): Promise<ChatSession> => {
    const response = await client.get(`/chat/sessions/${sessionId}`);

    return response.data;
  },

  createSession: async (payload: CreateSessionRequest): Promise<ChatSession> => {
    const response = await client.post('/chat/sessions', payload);
    return response.data;
  },

  sendMessage: async (sessionId: string, content: string): Promise<ChatMessage> => {
    const response = await client.post(`/chat/sessions/${sessionId}/messages`, {
      content,
      role: 'user'
    });

    return response.data;
  },

  sendMessageStream: async (
    sessionId: string,
    content: string,
    model: string,
    onChunk: (chunk: string) => void,
    attachment_ids?: string[]
  ): Promise<void> => {
    const streamUrl = getStreamUrl(sessionId);
    const fetchOptions = getStreamFetchOptions(content, model, attachment_ids);
    const response = await performStreamFetch(streamUrl, fetchOptions);

    await doStreamProcessing(response, onChunk);
  },

  sendTrialMessageStream: async (
    content: string,
    onChunk: (chunk: string) => void
  ): Promise<void> => {
    const baseUrl = (import.meta.env.VITE_API_BASE_URL as string)?.replace(/\/+$/, '');
    const streamUrl = `${baseUrl}/chat/trial/stream`;
    const fetchOptions = {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive'
      },
      body: JSON.stringify({ content, role: 'user', model: 'standard' }),
    };

    const response = await fetch(streamUrl, fetchOptions);

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    await doStreamProcessing(response, onChunk);
  },
    
  deleteSession: async (sessionId: string): Promise<void> => {
    await client.delete(`/chat/sessions/${sessionId}`);
  },

  /**
   * Upload one or more files to a chat session.
   * Calls  POST /api/v1/chat/sessions/{sessionId}/attachments
   * Returns per-file results with attached: true/false and a human-readable message.
   */
  uploadAttachments: async (
    sessionId: string,
    files: File[]
  ): Promise<AttachmentUploadResponse> => {
    const formData = new FormData();
    files.forEach((file) => formData.append('files', file));

    const response = await client.post<AttachmentUploadResponse>(
      `/chat/sessions/${sessionId}/attachments`,
      formData,
      // Let Axios set Content-Type + boundary automatically
      { headers: { 'Content-Type': 'multipart/form-data' } }
    );

    return response.data;
  },
};

