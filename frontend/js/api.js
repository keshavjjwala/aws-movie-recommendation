// Thin wrapper around the backend API. window.API_BASE comes from config.js.
import { auth } from "./auth.js";

async function request(path, options = {}) {
  const headers = { "Content-Type": "application/json" };
  if (path.startsWith("/api/me/")) {
    const token = await auth.token();
    if (!token) throw Object.assign(new Error("Sign in to use your list."), { status: 401 });
    headers.Authorization = `Bearer ${token}`;
  }
  let response;
  try {
    response = await fetch((window.API_BASE || "") + path, { ...options, headers });
  } catch {
    throw new Error("Can't reach the server. Check that it's running and try again.");
  }
  if (response.status === 401 && headers.Authorization) {
    auth.signOut(); // the session expired or was revoked
    throw Object.assign(new Error("Your session has ended. Sign in again."), { status: 401 });
  }
  if (response.status === 204) return null;
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(typeof body.detail === "string" ? body.detail : `The server rejected the request (${response.status}).`);
  }
  return body;
}

const q = encodeURIComponent;
const send = (method, body) => ({ method, body: body && JSON.stringify(body) });

export const api = {
  popular: (limit = 40) => request(`/api/movies/popular?limit=${limit}`),
  search: (text, limit = 48) => request(`/api/movies/search?q=${q(text)}&limit=${limit}`),
  movie: (id) => request(`/api/movies/${id}`),
  similar: (id, limit = 20) => request(`/api/movies/${id}/similar?limit=${limit}`),

  library: () => request("/api/me/library"),
  recommendations: (limit = 30) => request(`/api/me/recommendations?limit=${limit}`),
  stats: () => request("/api/me/stats"),
  setStatus: (id, status) => request(`/api/me/library/${id}/status`, send("PUT", { status })),
  rate: (id, rating) => request(`/api/me/library/${id}/rating`, send("PUT", { rating })),
  unrate: (id) => request(`/api/me/library/${id}/rating`, send("DELETE")),
  remove: (id) => request(`/api/me/library/${id}`, send("DELETE")),
};
