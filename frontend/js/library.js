// The signed-in user's movie list: movie id -> movie summary + status + rating.
import { api } from "./api.js";
import { auth } from "./auth.js";

export const STATUSES = [
  { id: "watching", label: "Watching" },
  { id: "plan_to_watch", label: "Plan to watch" },
  { id: "watched", label: "Watched" },
  { id: "dropped", label: "Dropped" },
];
export const statusLabel = (id) => STATUSES.find((s) => s.id === id)?.label ?? "";

const SKIP_KEY = "movie-picks-skipped-welcome";
const listeners = new Set();

function skipped() {
  try {
    return (localStorage.getItem(SKIP_KEY) || "").split(",").includes(auth.email);
  } catch {
    return false;
  }
}

export const library = {
  entries: new Map(),
  loadedFor: null, // email the entries belong to

  get loaded() {
    return !auth.signedIn || this.loadedFor === auth.email;
  },

  async load() {
    if (!auth.signedIn) return this.clear();
    const entries = await api.library();
    this.entries = new Map(entries.map((m) => [m.id, m]));
    this.loadedFor = auth.email;
    emit();
  },

  clear() {
    this.entries = new Map();
    this.loadedFor = null;
    emit();
  },

  get: (id) => library.entries.get(id) ?? null,
  ratingOf: (id) => library.entries.get(id)?.rating ?? 0,
  statusOf: (id) => library.entries.get(id)?.status ?? null,
  withStatus: (status) => [...library.entries.values()].filter((m) => m.status === status),

  loved() {
    return [...this.entries.values()].filter((m) => m.rating >= 4).sort((a, b) => b.rating - a.rating);
  },

  needsWelcome() {
    return auth.signedIn && this.loved().length < 3 && !skipped();
  },

  skipWelcome() {
    try {
      localStorage.setItem(SKIP_KEY, [...(localStorage.getItem(SKIP_KEY) || "").split(","), auth.email].join(","));
    } catch {
      // blocked storage: we'll offer the picker again next visit
    }
  },

  async setStatus(movie, status) {
    await api.setStatus(movie.id, status);
    this._put(movie, { status });
  },

  async rate(movie, rating) {
    await api.rate(movie.id, rating);
    const status = this.statusOf(movie.id);
    this._put(movie, { rating, status: !status || status === "plan_to_watch" ? "watched" : status });
  },

  async unrate(movie) {
    await api.unrate(movie.id);
    if (this.entries.has(movie.id)) this._put(movie, { rating: null });
  },

  async remove(movie) {
    await api.remove(movie.id);
    this.entries.delete(movie.id);
    emit();
  },

  _put(movie, changes) {
    const { score, because, ...summary } = movie;
    const current = this.entries.get(movie.id) ?? { ...summary, rating: null };
    this.entries.delete(movie.id); // re-insert so the newest change comes first
    this.entries = new Map([[movie.id, { ...current, ...changes, updated: new Date().toISOString() }], ...this.entries]);
    emit();
  },

  subscribe(fn) {
    listeners.add(fn);
    return () => listeners.delete(fn);
  },
};

function emit() {
  listeners.forEach((fn) => fn(library));
}
