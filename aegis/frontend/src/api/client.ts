import axios from "axios";

// VITE_API_URL must point to the backend (e.g. http://localhost:8000).
// Without it, requests go to the Vite dev server origin and 404.
// Set in frontend/.env or docker-compose environment.
const API_BASE = import.meta.env.VITE_API_URL || "";

const client = axios.create({
  baseURL: `${API_BASE}/api/v1`,
  headers: { "Content-Type": "application/json" },
});

// Attach API key from localStorage if the user has set one.
// In dev mode (AEGIS_API_KEY=dev-key), auth is skipped on the backend.
client.interceptors.request.use((config) => {
  const key = localStorage.getItem("aegis_api_key");
  if (key) {
    config.headers["X-API-Key"] = key;
  }
  return config;
});

export default client;
