import axios from 'axios';
import toast from 'react-hot-toast';

const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:3001/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to append tenant_id from URL
client.interceptors.request.use(
  (config) => {
    try {
      const url = new URL(window.location.href);
      const tenantId = url.searchParams.get('tenant_id');

      if (tenantId && tenantId.trim() !== '') {
        if (!config.params) {
          config.params = {};
        }
        config.params.tenant_id = tenantId;
      }
    } catch (error) {
      console.error('Failed to parse URL for tenant_id:', error);
    }

    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor for error handling
client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      switch (error.response.status) {
        case 401:
          toast.error('Unauthorized. Please check your credentials.');
          break;
        case 403:
          toast.error('Access denied');
          break;
        case 500:
          toast.error('Server error. Please try again later.');
          break;
      }
    } else if (error.request) {
      toast.error('Network error. Please check your connection.');
    }

    return Promise.reject(error);
  }
);

export default client;
