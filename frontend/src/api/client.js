import axios from 'axios';

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 90000,
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response) {
      return Promise.reject(err.response.data);
    }
    return Promise.reject(err);
  },
);

export default api;
