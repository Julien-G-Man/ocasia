import axios from "axios";

const DJANGO_API_URL = import.meta.env.VITE_DJANGO_API_URL;
const FASTAPI_URL = import.meta.env.VITE_FASTAPI_URL;

if (!DJANGO_API_URL) {
  throw new Error("Missing VITE_DJANGO_API_URL in environment");
}

if (!FASTAPI_URL) {
  throw new Error("Missing VITE_FASTAPI_URL in environment");
}

const DJANGO_ROOT_URL = DJANGO_API_URL.replace(/\/api\/?$/, ""); // strip /api 

const djangoApi = axios.create({
  baseURL: DJANGO_API_URL,
  timeout: 20000,
  headers: {
    "Content-Type": "application/json",
  },
});

djangoApi.interceptors.request.use((config) => {
  const token = localStorage.getItem("auth_token");
  if (token) config.headers.Authorization = `Token ${token}`;
  return config;
});

export const DJANGO_HEALTH_ENDPOINT = `${DJANGO_ROOT_URL}/health/`;
export const DJANGO_WARMUP_ENDPOINT = `${DJANGO_ROOT_URL}/warmup/`;
export const FASTAPI_HEALTH_ENDPOINT = `${FASTAPI_URL}/health`;

export const getApiErrorMessage = (error, fallback = "Something went wrong.") => {
  if (!error) return fallback;
  const detail = error?.response?.data?.detail;
  if (typeof detail === "string" && detail.trim()) return detail;

  const message = error?.response?.data?.error;
  if (typeof message === "string" && message.trim()) return message;

  const validationDetails = error?.response?.data?.details;
  if (validationDetails && typeof validationDetails === "object") {
    const firstKey = Object.keys(validationDetails)[0];
    const firstValue = validationDetails[firstKey];
    if (Array.isArray(firstValue) && firstValue.length) {
      return `${firstKey}: ${String(firstValue[0])}`;
    }
  }

  if (error?.code === "ECONNABORTED") return "Request timed out. Please try again.";
  if (typeof error?.message === "string" && error.message.trim()) return error.message;
  return fallback;
};

export default djangoApi;
