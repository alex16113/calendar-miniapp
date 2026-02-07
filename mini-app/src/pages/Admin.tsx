import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { api, type AdminPendingItem, type AdminSettings } from "../api";
import { haptic } from "../utils/haptic";

const WEEKDAY_LABELS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];
const WEEKDAY_KEYS = ["0", "1", "2", "3", "4", "5", "6"];

/** Быстрый выбор таймзоны (как в боте) */
const TZ_QUICK: { label: string; tz: string }[] = [
  { label: "Москва (MSK)", tz: "Europe/Moscow" },
  { label: "Калининград", tz: "Europe/Kaliningrad" },
  { label: "Екатеринбург", tz: "Asia/Yekaterinburg" },
  { label: "Новосибирск", tz: "Asia/Novosibirsk" },
  { label: "Иркутск", tz: "Asia/Irkutsk" },
  { label: "Якутск", tz: "Asia/Yakutsk" },
  { label: "Владивосток", tz: "Asia/Vladivostok" },
];

type AdminScreen = "menu" | "pending" | "timezone" | "work" | "buffer" | "blacklist" | "broadcast";

function formatWorkScheduleSummary(work_schedule: AdminSettings["work_schedule"]): string {
  const parts: string[] = [];
  for (const k of WEEKDAY_KEYS) {
    const d = work_schedule[k];
    if (!d?.enabled || !d.start || !d.end) continue;
    parts.push(`${d.start}-${d.end}`);
  }
  if (parts.length === 0) return "Не задано";
  const unique = [...new Set(parts)];
  return unique.length === 1 ? unique[0]! : unique.join(", ");
}

export default function Admin() {
  const [screen, setScreen] = useState<AdminScreen>("menu");
  const [settings, setSettings] = useState<AdminSettings | null>(null);
  const [settingsLoading, setSettingsLoading] = useState(true);
  const [pending, setPending] = useState<AdminPendingItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [pendingLoading, setPendingLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);
  const limit = 10;

  // Загрузка настроек при входе (проверка прав через getSettings)
  useEffect(() => {
    let cancelled = false;
    setSettingsLoading(true);
    setError(null);
    setForbidden(false);
    api.admin
      .getSettings()
      .then((res) => {
        if (!cancelled) setSettings(res);
      })
      .catch((e) => {
        if (!cancelled) {
          if (e.message && (e.message.includes("403") || e.message.includes("Admin"))) {
            setForbidden(true);
          } else {
            setError(e.message || "Ошибка загрузки");
          }
        }
      })
      .finally(() => {
        if (!cancelled) setSettingsLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  // Загрузка pending при открытии экрана «Ожидающие заявки»
  useEffect(() => {
    if (screen !== "pending") return;
    let cancelled = false;
    setPendingLoading(true);
    api.admin
      .getPending(page, limit)
      .then((res) => {
        if (!cancelled) {
          setPending(res.items);
          setTotal(res.total);
        }
      })
      .catch((e) => {
        if (!cancelled) setError(e.message || "Ошибка загрузки");
      })
      .finally(() => {
        if (!cancelled) setPendingLoading(false);
      });
    return () => { cancelled = true; };
  }, [screen, page]);

  const goToMenu = () => {
    setScreen("menu");
    setError(null);
    if (settings) api.admin.getSettings().then(setSettings).catch(() => {});
  };

  const removeFromList = (id: number) => {
    setPending((prev) => prev.filter((m) => m.id !== id));
    setTotal((t) => Math.max(0, t - 1));
  };

  const handleConfirm = (id: number) => {
    haptic.medium();
    api.admin
      .confirmMeeting(id)
      .then(() => {
        haptic.success();
        removeFromList(id);
      })
      .catch((e) => {
        haptic.error();
        alert(e.message || "Ошибка");
      });
  };

  const handleReject = (id: number) => {
    if (!confirm("Отклонить заявку?")) return;
    haptic.medium();
    api.admin
      .rejectMeeting(id)
      .then(() => {
        haptic.success();
        removeFromList(id);
      })
      .catch((e) => {
        haptic.error();
        alert(e.message || "Ошибка");
      });
  };

  const handleBan = (id: number) => {
    if (!confirm("Отклонить и добавить пользователя в бан?")) return;
    haptic.medium();
    api.admin
      .banMeeting(id)
      .then(() => {
        haptic.success();
        removeFromList(id);
      })
      .catch((e) => {
        haptic.error();
        alert(e.message || "Ошибка");
      });
  };

  if (forbidden) {
    return (
      <>
        <div className="mesh-gradient-bg" />
        <div className="page">
          <Link to="/" className="page-back">← Назад</Link>
          <h1 className="page-title">Админ-панель</h1>
          <div className="glass-panel glass-empty">
            <div className="glass-empty-icon">🔒</div>
            <div className="glass-empty-title">Доступ запрещён</div>
            <div className="glass-empty-text">
              Эта страница доступна только администратору.
            </div>
          </div>
          <Link to="/" className="glass-btn glass-btn-accent" style={{ marginTop: 16 }}>
            На главную
          </Link>
        </div>
      </>
    );
  }

  return (
    <>
      <div className="mesh-gradient-bg" />
      <div className="page">
        <Link to="/" className="page-back">← Назад</Link>
        <h1 className="page-title">Админ-панель</h1>

        {error && <div className="glass-error">{error}</div>}

        {screen === "menu" && (
          <AdminMenu
            settings={settings}
            settingsLoading={settingsLoading}
            onSelect={(s) => { haptic.selection(); setScreen(s); setError(null); }}
          />
        )}

        {screen === "pending" && (
          <AdminPendingList
            pending={pending}
            total={total}
            page={page}
            limit={limit}
            loading={pendingLoading}
            onPageChange={setPage}
            onBack={goToMenu}
            onConfirm={handleConfirm}
            onReject={handleReject}
            onBan={handleBan}
          />
        )}

        {screen === "timezone" && settings && (
          <AdminTimezone
            current={settings.timezone}
            onSaved={(tz) => { setSettings((s) => s ? { ...s, timezone: tz } : null); goToMenu(); }}
            onBack={goToMenu}
          />
        )}

        {screen === "work" && settings && (
          <AdminWorkSchedule
            workSchedule={settings.work_schedule}
            onScheduleUpdate={(ws) => setSettings((s) => s ? { ...s, work_schedule: ws } : null)}
            onBack={goToMenu}
          />
        )}

        {screen === "buffer" && settings && (
          <AdminBuffer
            current={settings.buffer_hours}
            onSaved={(buf) => { setSettings((s) => s ? { ...s, buffer_hours: buf } : null); goToMenu(); }}
            onBack={goToMenu}
          />
        )}

        {screen === "blacklist" && settings && (
          <AdminBlacklist
            dates={settings.blacklist_dates}
            onChanged={() => api.admin.getSettings().then(setSettings)}
            onBack={goToMenu}
          />
        )}

        {screen === "broadcast" && (
          <AdminBroadcast onBack={goToMenu} />
        )}
      </div>
    </>
  );
}

function AdminMenu({
  settings,
  settingsLoading,
  onSelect,
}: {
  settings: AdminSettings | null;
  settingsLoading: boolean;
  onSelect: (screen: AdminScreen) => void;
}) {
  if (settingsLoading || !settings) {
    return (
      <div className="glass-loading">
        <span className="spinner" />
        Загрузка настроек...
      </div>
    );
  }
  const workSummary = formatWorkScheduleSummary(settings.work_schedule);
  return (
    <>
      <div className="glass-panel" style={{ marginBottom: 16 }}>
        <div style={{ fontSize: 14, color: "var(--tg-hint)", marginBottom: 4 }}>Таймзона</div>
        <div style={{ fontWeight: 600 }}>{settings.timezone}</div>
        <div style={{ fontSize: 14, color: "var(--tg-hint)", marginBottom: 4, marginTop: 12 }}>Рабочие часы</div>
        <div style={{ fontWeight: 600 }}>{workSummary}</div>
        <div style={{ fontSize: 14, color: "var(--tg-hint)", marginBottom: 4, marginTop: 12 }}>Буфер</div>
        <div style={{ fontWeight: 600 }}>{settings.buffer_hours} ч</div>
      </div>
      <p className="page-section-label">Выбери, что изменить:</p>
      <div className="glass-panel">
        <button type="button" className="glass-btn" onClick={() => onSelect("timezone")}>
          🌍 Таймзона
        </button>
        <button type="button" className="glass-btn" onClick={() => onSelect("work")}>
          🕒 Рабочие часы
        </button>
        <button type="button" className="glass-btn" onClick={() => onSelect("buffer")}>
          ⏳ Буфер (часы)
        </button>
        <button type="button" className="glass-btn" onClick={() => onSelect("blacklist")}>
          🚫 Blacklist дат
        </button>
        <button type="button" className="glass-btn" onClick={() => onSelect("pending")}>
          📁 Список ожидания (pending)
        </button>
        <button type="button" className="glass-btn" onClick={() => onSelect("broadcast")}>
          🔔 Broadcast
        </button>
      </div>
    </>
  );
}

function AdminPendingList({
  pending,
  total,
  page,
  limit,
  loading,
  onPageChange,
  onBack,
  onConfirm,
  onReject,
  onBan,
}: {
  pending: AdminPendingItem[];
  total: number;
  page: number;
  limit: number;
  loading: boolean;
  onPageChange: (p: number) => void;
  onBack: () => void;
  onConfirm: (id: number) => void;
  onReject: (id: number) => void;
  onBan: (id: number) => void;
}) {
  return (
    <>
      <button type="button" className="glass-btn glass-btn-muted" style={{ marginBottom: 16 }} onClick={onBack}>
        ← В меню
      </button>
      <p className="page-section-label">Ожидающие заявки</p>
      {loading && pending.length === 0 ? (
        <div className="glass-loading">
          <span className="spinner" />
          Загрузка заявок...
        </div>
      ) : pending.length === 0 ? (
        <div className="glass-panel glass-empty">
          <div className="glass-empty-icon">✓</div>
          <div className="glass-empty-title">Нет заявок в ожидании</div>
          <div className="glass-empty-text">
            Все заявки обработаны. Новые появятся здесь автоматически.
          </div>
        </div>
      ) : (
        <>
          <div className="glass-panel" style={{ padding: 0 }}>
            {pending.map((m, idx) => (
              <div
                key={m.id}
                className="meeting-card meeting-card-even"
                style={{ marginBottom: idx < pending.length - 1 ? 8 : 0, marginLeft: 0, marginRight: 0 }}
              >
                <div style={{ marginBottom: 12 }}>
                  <div style={{ fontWeight: 600, fontSize: 16, marginBottom: 4 }}>{m.start_local}</div>
                  <div style={{ fontSize: 14, color: "var(--tg-hint)" }}>
                    {m.user_name || "—"} · {m.subject || "Без темы"}
                  </div>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                  <button type="button" className="glass-btn glass-btn-accent" onClick={() => onConfirm(m.id)}>
                    ✓ Подтвердить
                  </button>
                  <button type="button" className="glass-btn glass-btn-muted" onClick={() => onReject(m.id)}>
                    ✕ Отклонить
                  </button>
                  <button
                    type="button"
                    className="glass-btn"
                    style={{ gridColumn: "1 / -1", background: "rgba(255,59,48,0.2)", color: "var(--destructive)" }}
                    onClick={() => onBan(m.id)}
                  >
                    🚫 Отклонить и заблокировать
                  </button>
                </div>
              </div>
            ))}
          </div>
          {total > limit && (
            <div style={{ display: "flex", gap: 12, marginTop: 16, alignItems: "center", justifyContent: "center", flexWrap: "wrap" }}>
              <button
                type="button"
                className="glass-btn glass-btn-muted"
                disabled={page === 0}
                onClick={() => onPageChange(page - 1)}
              >
                ← Назад
              </button>
              <span style={{ color: "var(--tg-hint)", fontSize: 14 }}>
                {page + 1} из {Math.ceil(total / limit)}
              </span>
              <button
                type="button"
                className="glass-btn glass-btn-muted"
                disabled={page >= Math.ceil(total / limit) - 1}
                onClick={() => onPageChange(page + 1)}
              >
                Вперёд →
              </button>
            </div>
          )}
        </>
      )}
    </>
  );
}

function AdminTimezone({
  current,
  onSaved,
  onBack,
}: {
  current: string;
  onSaved: (tz: string) => void;
  onBack: () => void;
}) {
  const [sub, setSub] = useState<"list" | "custom">("list");
  const [customValue, setCustomValue] = useState(current);
  const [saving, setSaving] = useState(false);
  const [loadingGoogle, setLoadingGoogle] = useState(false);

  const applyTz = (tz: string) => {
    setSaving(true);
    api.admin
      .putTimezone(tz)
      .then(() => { haptic.success(); onSaved(tz); })
      .catch((e) => { haptic.error(); alert(e.message || "Ошибка"); })
      .finally(() => setSaving(false));
  };

  if (sub === "custom") {
    return (
      <>
        <button type="button" className="glass-btn glass-btn-muted" style={{ marginBottom: 16 }} onClick={() => setSub("list")}>
          ← Назад
        </button>
        <p className="page-section-label">Введи таймзону (например Europe/Moscow)</p>
        <div className="glass-panel">
          <input
            className="glass-input"
            value={customValue}
            onChange={(e) => setCustomValue(e.target.value)}
            placeholder="Europe/Moscow"
          />
          <button
            type="button"
            className="glass-btn glass-btn-accent"
            style={{ marginTop: 12 }}
            disabled={saving || !customValue.trim()}
            onClick={() => applyTz(customValue.trim())}
          >
            {saving ? "Сохранение..." : "Сохранить"}
          </button>
        </div>
      </>
    );
  }

  return (
    <>
      <button type="button" className="glass-btn glass-btn-muted" style={{ marginBottom: 16 }} onClick={onBack}>
        ← В меню
      </button>
      <p className="page-section-label">Выбери таймзону:</p>
      <div className="glass-panel">
        <button
          type="button"
          className="glass-btn"
          disabled={loadingGoogle}
          onClick={() => {
            setLoadingGoogle(true);
            api.admin
              .getTimezoneGoogle()
              .then((res) => applyTz(res.timezone))
              .catch((e) => { haptic.error(); alert(e.message || "Не удалось взять из Google"); })
              .finally(() => setLoadingGoogle(false));
          }}
        >
          🗓️ Взять из Google Calendar
        </button>
        {TZ_QUICK.map(({ label, tz }) => (
          <button
            key={tz}
            type="button"
            className="glass-btn"
            disabled={saving}
            onClick={() => applyTz(tz)}
          >
            {label}
          </button>
        ))}
        <button type="button" className="glass-btn" onClick={() => setSub("custom")}>
          ✍️ Другая…
        </button>
      </div>
    </>
  );
}

function AdminWorkSchedule({
  workSchedule,
  onScheduleUpdate,
  onBack,
}: {
  workSchedule: AdminSettings["work_schedule"];
  onScheduleUpdate: (ws: AdminSettings["work_schedule"]) => void;
  onBack: () => void;
}) {
  const [sub, setSub] = useState<"list" | "day" | "day_edit">("list");
  const [selectedWeekday, setSelectedWeekday] = useState(0);
  const [editStart, setEditStart] = useState("09:00");
  const [editEnd, setEditEnd] = useState("16:00");
  const [saving, setSaving] = useState(false);

  const buildPayload = (overrides?: { weekday: number; enabled: boolean; start?: string; end?: string }): Record<string, { enabled: boolean; start?: string; end?: string }> => {
    const payload: Record<string, { enabled: boolean; start?: string; end?: string }> = {};
    for (const k of WEEKDAY_KEYS) {
      const d = workSchedule[k];
      let enabled = d?.enabled ?? false;
      let start = (d?.start ?? "").trim() || "09:00";
      let end = (d?.end ?? "").trim() || "18:00";
      if (overrides && int(k) === overrides.weekday) {
        enabled = overrides.enabled;
        if (overrides.start != null) start = overrides.start;
        if (overrides.end != null) end = overrides.end;
      }
      payload[k] = { enabled, ...(enabled ? { start, end } : {}) };
    }
    return payload;
  };

  const savePayload = (payload: Record<string, { enabled: boolean; start?: string; end?: string }>) => {
    setSaving(true);
    api.admin
      .putWorkSchedule(payload)
      .then(() => { haptic.success(); onScheduleUpdate(payload); })
      .catch((e) => { haptic.error(); alert(e.message); })
      .finally(() => setSaving(false));
  };

  const handleSetHours = () => {
    if (editStart >= editEnd) {
      alert("Начало должно быть раньше конца.");
      return;
    }
    const payload = buildPayload({ weekday: selectedWeekday, enabled: true, start: editStart, end: editEnd });
    savePayload(payload);
    setSub("list");
  };

  const handleSetOff = () => {
    const payload = buildPayload({ weekday: selectedWeekday, enabled: false });
    savePayload(payload);
    setSub("list");
  };

  const k = String(selectedWeekday);
  const dayItem = workSchedule[k];
  const dayEnabled = dayItem?.enabled ?? false;
  const dayStart = (dayItem?.start ?? "").trim() || "09:00";
  const dayEnd = (dayItem?.end ?? "").trim() || "18:00";
  const dayLabel = WEEKDAY_LABELS[selectedWeekday]!;

  if (sub === "day_edit") {
    return (
      <>
        <button type="button" className="glass-btn glass-btn-muted" style={{ marginBottom: 16 }} onClick={() => setSub("day")}>
          ← Назад
        </button>
        <p className="page-section-label">{dayLabel}: введи часы (HH:MM–HH:MM)</p>
        <div className="glass-panel">
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <input
              type="time"
              className="glass-input"
              style={{ flex: 1 }}
              value={editStart}
              onChange={(e) => setEditStart(e.target.value)}
            />
            <span style={{ color: "var(--tg-hint)" }}>–</span>
            <input
              type="time"
              className="glass-input"
              style={{ flex: 1 }}
              value={editEnd}
              onChange={(e) => setEditEnd(e.target.value)}
            />
          </div>
          <button type="button" className="glass-btn glass-btn-accent" style={{ marginTop: 12 }} disabled={saving} onClick={handleSetHours}>
            {saving ? "Сохранение..." : "Сохранить"}
          </button>
        </div>
      </>
    );
  }

  if (sub === "day") {
    return (
      <>
        <button type="button" className="glass-btn glass-btn-muted" style={{ marginBottom: 16 }} onClick={() => setSub("list")}>
          ← Назад к дням
        </button>
        <div className="glass-panel" style={{ marginBottom: 16 }}>
          <div style={{ fontWeight: 600, fontSize: 18 }}>
            {dayLabel}: {dayEnabled ? `${dayStart}–${dayEnd}` : "выходной"}
          </div>
        </div>
        <div className="glass-panel">
          <button type="button" className="glass-btn" disabled={saving} onClick={() => { setEditStart(dayStart); setEditEnd(dayEnd); setSub("day_edit"); }}>
            🕒 Задать часы
          </button>
          <button type="button" className="glass-btn" disabled={saving} onClick={handleSetOff}>
            🏖️ Выходной
          </button>
        </div>
      </>
    );
  }

  return (
    <>
      <button type="button" className="glass-btn glass-btn-muted" style={{ marginBottom: 16 }} onClick={onBack}>
        ← В меню
      </button>
      <p className="page-section-label">Выбери день недели:</p>
      <div className="glass-panel" style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8 }}>
        {WEEKDAY_KEYS.map((key, i) => (
          <button
            key={key}
            type="button"
            className="glass-btn"
            onClick={() => { setSelectedWeekday(i); setSub("day"); setEditStart((workSchedule[key]?.start ?? "").trim() || "09:00"); setEditEnd((workSchedule[key]?.end ?? "").trim() || "18:00"); }}
          >
            {WEEKDAY_LABELS[i]}
          </button>
        ))}
      </div>
    </>
  );
}

function int(s: string): number {
  return parseInt(s, 10);
}

function AdminBuffer({
  current,
  onSaved,
  onBack,
}: {
  current: number;
  onSaved: (buf: number) => void;
  onBack: () => void;
}) {
  const [value, setValue] = useState(String(current));
  const [saving, setSaving] = useState(false);
  const handleSave = () => {
    const n = parseInt(value, 10);
    if (Number.isNaN(n) || n < 0 || n > 24) {
      alert("Введите число от 0 до 24");
      return;
    }
    setSaving(true);
    api.admin
      .putBufferHours(n)
      .then(() => { haptic.success(); onSaved(n); })
      .catch((e) => { haptic.error(); alert(e.message); })
      .finally(() => setSaving(false));
  };
  return (
    <>
      <button type="button" className="glass-btn glass-btn-muted" style={{ marginBottom: 16 }} onClick={onBack}>
        ← В меню
      </button>
      <div className="glass-form-group">
        <label className="glass-form-label">Буфер (часы, 0–24)</label>
        <input
          type="number"
          min={0}
          max={24}
          className="glass-input"
          value={value}
          onChange={(e) => setValue(e.target.value)}
        />
      </div>
      <button type="button" className="glass-btn glass-btn-accent" disabled={saving} onClick={handleSave}>
        {saving ? "Сохранение..." : "Сохранить"}
      </button>
    </>
  );
}

function AdminBlacklist({
  dates,
  onChanged,
  onBack,
}: {
  dates: { date: string; reason: string | null }[];
  onChanged: () => void;
  onBack: () => void;
}) {
  const [addDate, setAddDate] = useState("");
  const [addReason, setAddReason] = useState("");
  const [adding, setAdding] = useState(false);
  const handleAdd = () => {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(addDate.trim())) {
      alert("Формат даты: ГГГГ-ММ-ДД");
      return;
    }
    setAdding(true);
    api.admin
      .addBlacklistDate(addDate.trim(), addReason.trim() || null)
      .then(() => {
        haptic.success();
        setAddDate("");
        setAddReason("");
        onChanged();
      })
      .catch((e) => { haptic.error(); alert(e.message); })
      .finally(() => setAdding(false));
  };
  const handleRemove = (dateStr: string) => {
    if (!confirm("Удалить дату из blacklist?")) return;
    api.admin
      .removeBlacklistDate(dateStr)
      .then(() => { haptic.success(); onChanged(); })
      .catch((e) => { haptic.error(); alert(e.message); });
  };
  return (
    <>
      <button type="button" className="glass-btn glass-btn-muted" style={{ marginBottom: 16 }} onClick={onBack}>
        ← В меню
      </button>
      <p className="page-section-label">Добавить дату</p>
      <div className="glass-panel">
        <div className="glass-form-group">
          <label className="glass-form-label">Дата (ГГГГ-ММ-ДД)</label>
          <input
            className="glass-input"
            placeholder="2026-02-15"
            value={addDate}
            onChange={(e) => setAddDate(e.target.value)}
          />
        </div>
        <div className="glass-form-group">
          <label className="glass-form-label">Причина (необязательно)</label>
          <input
            className="glass-input"
            placeholder="Выходной"
            value={addReason}
            onChange={(e) => setAddReason(e.target.value)}
          />
        </div>
        <button type="button" className="glass-btn glass-btn-accent" disabled={adding} onClick={handleAdd}>
          {adding ? "Добавление..." : "Добавить"}
        </button>
      </div>
      <p className="page-section-label" style={{ marginTop: 20 }}>Даты в blacklist</p>
      {dates.length === 0 ? (
        <div className="glass-panel glass-empty">
          <div className="glass-empty-text">Нет дат</div>
        </div>
      ) : (
        <div className="glass-panel" style={{ padding: 0 }}>
          {dates.map(({ date, reason }) => (
            <div
              key={date}
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                padding: "12px 16px",
                borderBottom: "1px solid var(--border-color)",
              }}
            >
              <div>
                <span style={{ fontWeight: 600 }}>{date}</span>
                {reason && <span style={{ marginLeft: 8, color: "var(--tg-hint)", fontSize: 14 }}>{reason}</span>}
              </div>
              <button type="button" className="glass-btn glass-btn-muted" onClick={() => handleRemove(date)}>
                Удалить
              </button>
            </div>
          ))}
        </div>
      )}
    </>
  );
}

function AdminBroadcast({ onBack }: { onBack: () => void }) {
  const [date, setDate] = useState("");
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState<{ sent: number; failed: number; total: number } | null>(null);
  const handleSend = () => {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date.trim())) {
      alert("Формат даты: ГГГГ-ММ-ДД");
      return;
    }
    if (!text.trim()) {
      alert("Введите текст сообщения");
      return;
    }
    setSending(true);
    setResult(null);
    api.admin
      .broadcast(date.trim(), text.trim())
      .then((res) => {
        haptic.success();
        setResult(res);
      })
      .catch((e) => {
        haptic.error();
        alert(e.message);
      })
      .finally(() => setSending(false));
  };
  return (
    <>
      <button type="button" className="glass-btn glass-btn-muted" style={{ marginBottom: 16 }} onClick={onBack}>
        ← В меню
      </button>
      <p className="page-section-label">Рассылка на дату</p>
      <div className="glass-panel">
        <div className="glass-form-group">
          <label className="glass-form-label">Дата встреч (ГГГГ-ММ-ДД)</label>
          <input
            className="glass-input"
            placeholder="2026-02-15"
            value={date}
            onChange={(e) => setDate(e.target.value)}
          />
        </div>
        <div className="glass-form-group">
          <label className="glass-form-label">Текст сообщения</label>
          <textarea
            className="glass-input"
            rows={4}
            placeholder="Напоминание о встрече..."
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
        </div>
        <button type="button" className="glass-btn glass-btn-accent" disabled={sending} onClick={handleSend}>
          {sending ? "Отправка..." : "Отправить"}
        </button>
      </div>
      {result && (
        <div className="glass-panel" style={{ marginTop: 16 }}>
          Отправлено: {result.sent}, ошибок: {result.failed}, всего получателей: {result.total}
        </div>
      )}
    </>
  );
}
