const TOKEN_KEY = "leran_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

/** Prefer same-origin /api (vite proxy); fall back to direct API if proxy dies. */
const DIRECT_API = "http://127.0.0.1:8000";

async function fetchWithFallback(path: string, options: RequestInit): Promise<Response> {
  try {
    return await fetch(path, options);
  } catch (err) {
    if (err instanceof TypeError && path.startsWith("/")) {
      // Failed to fetch via proxy → try direct API (CORS is open)
      return await fetch(DIRECT_API + path, options);
    }
    throw err;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers || {});
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (options.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  let res: Response;
  try {
    res = await fetchWithFallback(path, { ...options, headers });
  } catch (err) {
    const msg =
      err instanceof TypeError
        ? "网络请求失败（Failed to fetch）。API 8000 与 Vite 代理均不可达，请重启项目后硬刷新（Ctrl+Shift+R）。"
        : err instanceof Error
          ? err.message
          : "网络请求失败";
    throw new ApiError(0, msg);
  }
  if (res.status === 401) {
    setToken(null);
    if (!path.includes("/auth/")) {
      window.location.href = "/login";
    }
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = data.detail || JSON.stringify(data);
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, typeof detail === "string" ? detail : "Request failed");
  }
  if (res.status === 204) return undefined as T;
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) return res.json();
  return (await res.text()) as T;
}

export const api = {
  register: (email: string, password: string) =>
    request<{ id: number; email: string }>("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  login: async (email: string, password: string) => {
    const form = new URLSearchParams();
    form.set("username", email);
    form.set("password", password);
    const data = await request<{ access_token: string }>("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: form,
    });
    setToken(data.access_token);
    return data;
  },
  me: () => request<{ id: number; email: string }>("/api/auth/me"),
  today: () => request<TodayStats>("/api/today"),
  listMedia: () => request<MediaItem[]>("/api/media"),
  getMedia: (id: number) => request<MediaItem>(`/api/media/${id}`),
  uploadMedia: (file: File, title = "", onProgress?: (pct: number, label: string) => void) =>
    uploadMediaSmart(file, title, onProgress),
  uploadLimits: () => request<UploadLimits>("/api/media/limits"),
  reprocess: (id: number) => request<MediaItem>(`/api/media/${id}/reprocess`, { method: "POST" }),
  deleteMedia: (id: number) => request<{ ok: boolean }>(`/api/media/${id}`, { method: "DELETE" }),
  renameMedia: (id: number, title: string) =>
    request<MediaItem>(`/api/media/${id}`, { method: "PATCH", body: JSON.stringify({ title }) }),
  segments: (id: number) => request<Segment[]>(`/api/media/${id}/segments`),
  updateSegment: (id: number, body: Partial<{ edited_en: string; edited_zh: string; start_ms: number; end_ms: number }>) =>
    request<Segment>(`/api/media/segments/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  mediaFileUrl: (id: number) => `/api/media/${id}/file?token=${getToken() || ""}`,
  exportUrl: (id: number, format: string, lang: string) =>
    `/api/media/${id}/export?format=${format}&lang=${lang}`,
  downloadExport: async (id: number, format: string, lang: string) => {
    const res = await fetch(api.exportUrl(id, format, lang), {
      headers: { Authorization: `Bearer ${getToken()}` },
    });
    if (!res.ok) throw new ApiError(res.status, "Export failed");
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `media-${id}.${lang}.${format}`;
    a.click();
    URL.revokeObjectURL(url);
  },
  cardFromSegment: (segment_id: number, headword: string, meaning_zh = "", pos = "") =>
    request<Card>("/api/cards/from-segment", {
      method: "POST",
      body: JSON.stringify({ segment_id, headword, meaning_zh, pos }),
    }),
  listCards: (q = "") => request<Card[]>(`/api/cards?q=${encodeURIComponent(q)}`),
  deleteCard: (id: number) => request<{ ok: boolean }>(`/api/cards/${id}`, { method: "DELETE" }),
  createCard: (body: { headword: string; meaning_zh?: string; pos?: string }) =>
    request<Card>("/api/cards", { method: "POST", body: JSON.stringify(body) }),
  graphWord: (word: string) =>
    request<GraphData>(`/api/graph/word?word=${encodeURIComponent(word)}`),
  decks: () => request<Deck[]>("/api/decks"),
  reviewQueue: (limit = 20) => request<ReviewItem[]>(`/api/review/queue?limit=${limit}`),
  stories: () => request<Story[]>("/api/stories"),
  generateStory: (day: string, words: string[]) =>
    request<Story>("/api/stories", {
      method: "POST",
      body: JSON.stringify({ day, words }),
    }),
  deleteStory: (id: number) => request<{ ok: boolean }>(`/api/stories/${id}`, { method: "DELETE" }),
  submitReview: (cardId: number, rating: number, duration_ms = 0) =>
    request<Card>(`/api/review/${cardId}`, {
      method: "POST",
      body: JSON.stringify({ rating, duration_ms }),
    }),
  providers: () => request<ProviderRow[]>("/api/settings/providers"),
  saveProvider: (body: { kind: string; provider_id: string; api_key?: string; base_url?: string; model?: string }) =>
    request<ProviderRow>("/api/settings/providers", { method: "PUT", body: JSON.stringify(body) }),
  testProvider: (body: {
    kind: string;
    provider_id?: string;
    api_key?: string;
    base_url?: string;
    model?: string;
  }) =>
    request<{ ok: boolean; kind: string; provider_id: string; message: string; sample: string }>(
      "/api/settings/providers/test",
      { method: "POST", body: JSON.stringify(body) },
    ),
  downloadBlob: async (path: string, filename: string) => {
    const res = await fetch(path, { headers: { Authorization: `Bearer ${getToken()}` } });
    if (!res.ok) throw new ApiError(res.status, "Download failed");
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  },
  exportCardsCsv: () => api.downloadBlob("/api/export/cards.csv", "leran_cards.csv"),
  exportAnkiTsv: () => api.downloadBlob("/api/export/anki.tsv", "leran_cards.tsv"),
  exportAnkiZip: () => api.downloadBlob("/api/export/anki.zip", "leran_anki.zip"),
  cardAudioUrl: (cardId: number) =>
    `/api/cards/${cardId}/audio?token=${encodeURIComponent(getToken() || "")}`,
  mediaThumbUrl: (mediaId: number) =>
    `/api/media/${mediaId}/thumb?token=${encodeURIComponent(getToken() || "")}`,
  lookupWord: (word: string, segmentId?: number, deep = false) =>
    request<{
      word: string;
      ipa: string;
      pos: string;
      meaning_zh: string;
      meaning_en: string;
      example_en: string;
      example_zh: string;
      in_card: boolean;
      card_id: number | null;
      source: string;
    }>(
      `/api/lookup/word?word=${encodeURIComponent(word)}${
        segmentId != null ? `&segment_id=${segmentId}` : ""
      }${deep ? "&deep=1" : ""}`,
    ),
};

export type MediaStatus = "queued" | "extracting_audio" | "transcribing" | "translating" | "ready" | "failed";

export interface MediaItem {
  id: number;
  title: string;
  duration_ms: number;
  file_size: number;
  status: MediaStatus | string;
  progress?: string;
  error: string;
  asr_provider: string;
  translate_provider: string;
  created_at: string;
  updated_at: string;
  segment_count: number;
  card_count: number;
}

export interface UploadLimits {
  max_upload_mb: number;
  chunk_size_mb: number;
  max_upload_bytes: number;
  chunk_size_bytes: number;
}

const CHUNK_THRESHOLD = 8 * 1024 * 1024; // use chunked upload above 8MB

async function uploadMediaSmart(
  file: File,
  title = "",
  onProgress?: (pct: number, label: string) => void,
): Promise<MediaItem> {
  if (file.size <= CHUNK_THRESHOLD) {
    onProgress?.(50, "上传中");
    const fd = new FormData();
    fd.append("file", file);
    if (title) fd.append("title", title);
    const item = await request<MediaItem>("/api/media/upload", { method: "POST", body: fd });
    onProgress?.(100, "已入队");
    return item;
  }

  let limits: UploadLimits;
  try {
    limits = await request<UploadLimits>("/api/media/limits");
  } catch {
    limits = {
      max_upload_mb: 2048,
      chunk_size_mb: 8,
      max_upload_bytes: 2048 * 1024 * 1024,
      chunk_size_bytes: 8 * 1024 * 1024,
    };
  }
  if (file.size > limits.max_upload_bytes) {
    throw new ApiError(
      413,
      `文件过大（${(file.size / 1024 / 1024).toFixed(0)}MB），上限 ${limits.max_upload_mb}MB。可先用 ffmpeg 抽音频再上传。`,
    );
  }

  const chunkSize = limits.chunk_size_bytes || 8 * 1024 * 1024;
  const totalChunks = Math.ceil(file.size / chunkSize);
  onProgress?.(0, "初始化分片");
  const init = await request<{ upload_id: string }>("/api/media/upload/init", {
    method: "POST",
    body: JSON.stringify({
      upload_id: "",
      index: 0,
      total_chunks: totalChunks,
      total_size: file.size,
    }),
  });

  for (let i = 0; i < totalChunks; i++) {
    const start = i * chunkSize;
    const end = Math.min(file.size, start + chunkSize);
    const blob = file.slice(start, end);
    const fd = new FormData();
    fd.append("upload_id", init.upload_id);
    fd.append("index", String(i));
    fd.append("file", blob, file.name);
    await request<{ ok: boolean }>(`/api/media/upload/chunk`, { method: "POST", body: fd });
    onProgress?.(Math.round(((i + 1) / totalChunks) * 90), `上传分片 ${i + 1}/${totalChunks}`);
  }

  onProgress?.(95, "合并文件");
  const item = await request<MediaItem>("/api/media/upload/complete", {
    method: "POST",
    body: JSON.stringify({
      upload_id: init.upload_id,
      filename: file.name,
      title,
      total_size: file.size,
    }),
  });
  onProgress?.(100, "已入队");
  return item;
}

export interface WordSpan {
  text: string;
  start_ms: number;
  end_ms: number;
}

export interface Segment {
  id: number;
  media_id: number;
  idx: number;
  start_ms: number;
  end_ms: number;
  text_en: string;
  text_zh: string;
  raw_en: string;
  raw_zh: string;
  words: WordSpan[];
}

export interface Card {
  id: number;
  deck_id: number;
  headword: string;
  pos: string;
  ipa: string;
  meaning_zh: string;
  example_en: string;
  example_zh: string;
  media_id: number | null;
  segment_id: number | null;
  t_ms: number;
  audio_clip_key: string;
  tags: string;
  state: string;
  due_at: string;
  suspended: boolean;
  created_at: string;
  interval_days?: number;
  ease?: number;
  lapses?: number;
  reps?: number;
}

export interface Story {
  id: number;
  day: string;
  words: string[];
  content: string;
  created_at: string;
}

export interface GraphNode {
  word: string;
  label: string;
  zh: string;
}

export interface GraphRoot {
  root: string;
  meaning: string;
  words: GraphNode[];
}

export interface GraphData {
  word: string;
  ipa: string;
  pos: string;
  meaning_zh: string;
  groups: {
    inflections: GraphNode[];
    family: GraphNode[];
    similar: GraphNode[];
    roots: GraphRoot[];
  };
}

export interface Deck {
  id: number;
  name: string;
  description: string;
  is_default: boolean;
  card_count: number;
}

export interface ReviewItem {
  card: Card;
  media_id: number | null;
  t_ms: number;
  interval_previews?: number[]; // days: [Again, Hard, Good, Easy]
}

export interface WeekStat {
  date: string;
  new_words: number;
  reviews: number;
  minutes: number;
}

export interface TodayStats {
  due_count: number;
  new_count: number;
  learning_count: number;
  media_processing: number;
  media_ready: number;
  recent_media: MediaItem[];
  reviews_today: number;
  week: WeekStat[];
}

export interface ProviderRow {
  kind: string;
  provider_id: string;
  base_url: string;
  model: string;
  has_api_key: boolean;
}
