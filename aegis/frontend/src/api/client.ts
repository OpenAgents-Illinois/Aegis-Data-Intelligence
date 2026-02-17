import axios from "axios";

const API_BASE = import.meta.env.VITE_API_URL || "";

const client = axios.create({
  baseURL: `${API_BASE}/api/v1`,
  headers: { "Content-Type": "application/json" },
});

// Attach API key from localStorage
client.interceptors.request.use((config) => {
  const key = localStorage.getItem("aegis_api_key");
  if (key) {
    config.headers["X-API-Key"] = key;
  }
  return config;
});

export default client;
