import axios, { type InternalAxiosRequestConfig } from 'axios';

// Create an Axios instance
const client = axios.create({
  baseURL: (process.env.NEXT_PUBLIC_API_BASE_URL as string || '')?.replace(/\/+$/, ''),
  withCredentials: true, // Important for cookies
  headers: {
    'Content-Type': 'application/json',
  },
});

// Response interceptor to handle errors
const handleUnauthorizedError = async (error: { config: InternalAxiosRequestConfig & { _retry?: boolean } }) => {
  const originalRequest = error.config;

  originalRequest._retry = true;
  try {
    await client.get('/auth/refresh');

    return client(originalRequest);
  } catch (refreshError) {
    return Promise.reject(refreshError);
  }
};

client.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    const isUnauthorized = error.response && error.response.status === 401;
    const isAuthRoute = originalRequest.url?.includes('/auth/login') || originalRequest.url?.includes('/auth/signup');
    const canRetry = isUnauthorized && !originalRequest._retry && !originalRequest.url?.includes('/auth/refresh') && !isAuthRoute;

    if (canRetry) {
      return handleUnauthorizedError(error);
    }

    return Promise.reject(error);
  }
);

export default client;
