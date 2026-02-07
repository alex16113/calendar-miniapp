/**
 * API-клиент для бэкенда. Все запросы отправляют X-Telegram-Init-Data из WebApp.
 */

const API_BASE = import.meta.env.VITE_API_URL || "";

function getInitData(): string {
  const data = typeof window !== "undefined" && window.Telegram?.WebApp?.initData;
  
  // DEBUG: логируем для диагностики
  if (typeof window !== "undefined") {
    console.log("[API] Telegram object:", window.Telegram ? "exists" : "missing");
    console.log("[API] WebApp object:", window.Telegram?.WebApp ? "exists" : "missing");
    console.log("[API] initData length:", data ? data.length : 0);
    if (!data) {
      console.warn("[API] initData is empty! This will cause 422 errors.");
    }
  }
  
  if (!data) return "";
  return data;
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const initData = getInitData();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(typeof options.headers === "object" && !(options.headers instanceof Headers)
      ? (options.headers as Record<string, string>)
      : {}),
  };
  if (initData) headers["X-Telegram-Init-Data"] = initData;

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!res.ok) {
    const text = await res.text();
    console.error(`[API] Request failed: ${path}`, res.status, text);
    throw new Error(text || `HTTP ${res.status}`);
  }
  if (res.status === 204 || res.headers.get("content-length") === "0")
    return undefined as T;
  return res.json();
}

export interface WeekDay {
  date: string;
  has_slots: boolean;
}

export interface SlotsWeekResponse {
  week_start: string;
  days: WeekDay[];
}

export interface SlotsDayResponse {
  date: string;
  slots: string[];
}

export interface MyMeetingItem {
  id: number;
  status: string;
  start_time_utc: string;
  start_local: string;
  subject: string | null;
  duration: number;
  google_event_html_link: string | null;
}

export interface MyMeetingsResponse {
  total: number;
  page: number;
  limit: number;
  total_pages: number;
  items: MyMeetingItem[];
}

export const api = {
  getSlotsWeek: (weekOffset = 0, duration = 30) =>
    request<SlotsWeekResponse>(
      `/slots/week?week_offset=${weekOffset}&duration=${duration}`
    ),
  getSlotsDay: (date: string, duration = 30) =>
    request<SlotsDayResponse>(
      `/slots/day?date=${encodeURIComponent(date)}&duration=${duration}`
    ),
  postBooking: (body: {
    duration_minutes: number;
    date: string;
    time: string;
    name: string;
    subject: string;
    description?: string | null;
    email: string;
  }) => request<{ meeting_id: number }>("/booking", { method: "POST", body: JSON.stringify(body) }),
  getMyMeetings: (page = 0, limit = 10) =>
    request<MyMeetingsResponse>(`/my/meetings?page=${page}&limit=${limit}`),
  cancelMeeting: (meetingId: number) =>
    request<{ ok: boolean }>(`/my/meetings/${meetingId}/cancel`, { method: "POST" }),
  getMyProfile: () =>
    request<{ user_name: string | null; user_email: string | null }>("/my/profile"),

  // Admin (требует user_id == ADMIN_ID)
  admin: {
    getSettings: () => request<AdminSettings>("/admin/settings"),
    putTimezone: (timezone: string) =>
      request<{ ok: boolean }>("/admin/settings/timezone", { method: "PUT", body: JSON.stringify({ timezone }) }),
    getTimezoneGoogle: () =>
      request<{ timezone: string }>("/admin/settings/timezone/google"),
    putBufferHours: (buffer_hours: number) =>
      request<{ ok: boolean }>("/admin/settings/buffer_hours", { method: "PUT", body: JSON.stringify({ buffer_hours }) }),
    putWorkSchedule: (work_schedule: Record<string, { enabled: boolean; start?: string | null; end?: string | null }>) =>
      request<{ ok: boolean }>("/admin/settings/work_schedule", { method: "PUT", body: JSON.stringify({ work_schedule }) }),
    addBlacklistDate: (date: string, reason?: string | null) =>
      request<{ ok: boolean }>("/admin/settings/blacklist", { method: "POST", body: JSON.stringify({ date, reason: reason ?? null }) }),
    removeBlacklistDate: (dateStr: string) =>
      request<{ ok: boolean }>(`/admin/settings/blacklist/${encodeURIComponent(dateStr)}`, { method: "DELETE" }),
    getPending: (page = 0, limit = 10) =>
      request<AdminPendingResponse>(`/admin/pending?page=${page}&limit=${limit}`),
    confirmMeeting: (meetingId: number) =>
      request<{ ok: boolean }>(`/admin/meetings/${meetingId}/confirm`, { method: "POST" }),
    rejectMeeting: (meetingId: number, reason?: string) =>
      request<{ ok: boolean }>(`/admin/meetings/${meetingId}/reject`, {
        method: "POST",
        body: JSON.stringify({ reason: reason ?? null }),
      }),
    banMeeting: (meetingId: number) =>
      request<{ ok: boolean }>(`/admin/meetings/${meetingId}/ban`, { method: "POST" }),
    broadcast: (date: string, text: string) =>
      request<{ ok: boolean; sent: number; failed: number; total: number }>("/admin/broadcast", {
        method: "POST",
        body: JSON.stringify({ date, text }),
      }),
  },
};

export interface AdminSettings {
  timezone: string;
  buffer_hours: number;
  work_schedule: Record<string, { enabled: boolean; start?: string; end?: string }>;
  blacklist_dates: { date: string; reason: string | null }[];
}

export interface AdminPendingItem {
  id: number;
  user_id: number;
  username: string | null;
  user_name: string | null;
  user_email: string | null;
  subject: string | null;
  description: string | null;
  start_time_utc: string;
  start_local: string;
  duration: number;
}

export interface AdminPendingResponse {
  total: number;
  page: number;
  limit: number;
  total_pages: number;
  items: AdminPendingItem[];
}
