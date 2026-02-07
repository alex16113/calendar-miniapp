import { useState, useEffect } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, type WeekDay } from "../api";
import { haptic } from "../utils/haptic";

const DURATIONS = [15, 30, 60, 90] as const;
const WEEKDAY_NAMES = ["вс", "пн", "вт", "ср", "чт", "пт", "сб"];
const MONTH_NAMES = ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"];

function formatDayLabel(dateStr: string): string {
  const d = new Date(dateStr + "T12:00:00");
  const day = d.getDate();
  const month = MONTH_NAMES[d.getMonth()];
  const weekday = WEEKDAY_NAMES[d.getDay()];
  return `${weekday}, ${day} ${month}`;
}

/** Неделя по week_start (YYYY-MM-DD): "3–9 фев" или "28 фев – 6 мар" */
function formatWeekRange(weekStart: string): string {
  if (!weekStart) return "";
  const start = new Date(weekStart + "T12:00:00");
  const end = new Date(start);
  end.setDate(end.getDate() + 6);
  const d1 = start.getDate();
  const d2 = end.getDate();
  const m1 = MONTH_NAMES[start.getMonth()];
  const m2 = MONTH_NAMES[end.getMonth()];
  if (m1 === m2) return `${d1}–${d2} ${m1}`;
  return `${d1} ${m1} – ${d2} ${m2}`;
}

/** Подпись недели по смещению (0 = текущая, 1 = следующая) — всегда показываем, даже если API не ответил */
function getWeekRangeLabel(weekOffset: number): string {
  const now = new Date();
  const day = now.getDay();
  const toMonday = day === 0 ? -6 : 1 - day;
  const monday = new Date(now.getFullYear(), now.getMonth(), now.getDate() + toMonday);
  const start = new Date(monday);
  start.setDate(monday.getDate() + weekOffset * 7);
  const y = start.getFullYear();
  const m = String(start.getMonth() + 1).padStart(2, "0");
  const d = String(start.getDate()).padStart(2, "0");
  return formatWeekRange(`${y}-${m}-${d}`);
}

type Step = "duration" | "week" | "time" | "form" | "success";

export default function Booking() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [step, setStep] = useState<Step>("duration");
  const [duration, setDuration] = useState<number>(30);
  const [weekOffset, setWeekOffset] = useState(0);
  const [weekData, setWeekData] = useState<{ week_start: string; days: WeekDay[] } | null>(null);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [daySlots, setDaySlots] = useState<string[]>([]);
  const [selectedTime, setSelectedTime] = useState<string | null>(null);
  const [form, setForm] = useState({ name: "", subject: "", description: "", email: "" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [meetingId, setMeetingId] = useState<number | null>(null);

  // Открытие по прямой ссылке #/book?w=6 — сразу показываем шаг «неделя» с этим смещением
  useEffect(() => {
    const wParam = searchParams.get("w");
    if (wParam !== null && wParam !== "" && step === "duration") {
      const w = parseInt(wParam, 10);
      if (!Number.isNaN(w) && w >= 0) {
        setWeekOffset(w);
        setStep("week");
        setWeekData(null);
      }
    }
  }, [searchParams]);

  // Синхронизация weekOffset с URL при шаге week (после клика «Следующая неделя»)
  useEffect(() => {
    if (step !== "week") return;
    const w = parseInt(searchParams.get("w") ?? "", 10);
    if (!Number.isNaN(w) && w >= 0 && w !== weekOffset) {
      setWeekOffset(w);
      setWeekData(null);
    }
  }, [step, searchParams, weekOffset]);

  // При переходе на шаг week по кнопке «30 мин» выставляем в URL w=0, если ещё не задано
  useEffect(() => {
    if (step === "week" && searchParams.get("w") === null) {
      setSearchParams({ w: "0" }, { replace: true });
    }
  }, [step, searchParams, setSearchParams]);

  // Загрузка недели при шаге week
  useEffect(() => {
    if (step !== "week") return;
    let cancelled = false;
    setLoading(true);
    api
      .getSlotsWeek(weekOffset, duration)
      .then((data) => {
        if (!cancelled) setWeekData(data);
      })
      .catch((e) => {
        if (!cancelled) {
          console.error("Failed to load week slots", e);
          setWeekData({ week_start: "", days: [] });
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [step, weekOffset, duration]);

  // Загрузка слотов дня при выборе даты
  useEffect(() => {
    if (step !== "time" || !selectedDate) return;
    let cancelled = false;
    setLoading(true);
    api
      .getSlotsDay(selectedDate, duration)
      .then((data) => {
        if (!cancelled) setDaySlots(data.slots || []);
      })
      .catch((e) => {
        if (!cancelled) {
          console.error("Failed to load day slots", e);
          setDaySlots([]);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [step, selectedDate, duration]);

  const goBack = () => {
    setError(null);
    if (step === "week") setStep("duration");
    else if (step === "time") {
      setSelectedDate(null);
      setStep("week");
    } else if (step === "form") {
      setSelectedTime(null);
      setStep("time");
    }
  };

  const handleSubmitForm = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedDate || !selectedTime) return;
    const name = form.name.trim();
    const subject = form.subject.trim();
    const email = form.email.trim();
    if (!name || !subject || !email) {
      setError("Заполните имя, тему и email");
      return;
    }
    const emailRe = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRe.test(email)) {
      setError("Некорректный email");
      return;
    }
    setLoading(true);
    setError(null);
    api
      .postBooking({
        duration_minutes: duration,
        date: selectedDate,
        time: selectedTime,
        name,
        subject,
        description: form.description.trim() || null,
        email,
      })
      .then((res) => {
        haptic.success();
        setMeetingId(res.meeting_id);
        setStep("success");
      })
      .catch((e) => {
        haptic.error();
        setError(e.message || "Ошибка отправки");
      })
      .finally(() => setLoading(false));
  };

  const daysWithSlots = weekData?.days.filter((d) => d.has_slots) ?? [];

  return (
    <div>
      <h1>Новая встреча</h1>
      {step !== "success" && (
        <Link to="/" className="back-link">
          ← Назад
        </Link>
      )}

      {error && (
        <div className="error-message">{error}</div>
      )}

      {/* Шаг: длительность */}
      {step === "duration" && (
        <>
          <p className="section-title">Длительность встречи</p>
          <div className="group">
            {DURATIONS.map((m, idx) => (
              <div key={m} className="group-item" style={{ borderBottom: idx === DURATIONS.length - 1 ? "none" : undefined }}>
                <button
                  type="button"
                  className="btn"
                  onClick={() => {
                    haptic.selection();
                    setDuration(m);
                    setWeekOffset(0);
                    setWeekData(null);
                    setStep("week");
                  }}
                >
                  {m} минут
                </button>
              </div>
            ))}
          </div>
        </>
      )}

      {/* Шаг: выбор недели и дня */}
      {step === "week" && (
        <>
          <p className="section-title">
            Неделя {getWeekRangeLabel(weekOffset)}
          </p>
          {loading && !weekData ? (
            <div className="loading">
              <span className="spinner"></span>
              Загрузка доступных дней...
            </div>
          ) : daysWithSlots.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">📅</div>
              <div className="empty-state-title">Нет свободных дней</div>
              <div className="empty-state-text">
                На эту неделю свободных слотов нет. Попробуйте следующую.
              </div>
            </div>
          ) : (
            <div className="group">
              {daysWithSlots.map((d, idx) => (
                <div key={d.date} className="group-item" style={{ borderBottom: idx === daysWithSlots.length - 1 ? "none" : undefined }}>
                  <button
                    type="button"
                    className="btn"
                    onClick={() => {
                      haptic.selection();
                      setSelectedDate(d.date);
                      setStep("time");
                      setDaySlots([]);
                    }}
                  >
                    {formatDayLabel(d.date)}
                  </button>
                </div>
              ))}
            </div>
          )}
          <Link
            to={`/book?w=${weekOffset + 1}`}
            style={{ textDecoration: "none", display: "block", marginTop: 12 }}
          >
            <button type="button" className="btn btn-secondary">
              Следующая неделя →
            </button>
          </Link>
        </>
      )}

      {/* Шаг: выбор времени */}
      {step === "time" && selectedDate && (
        <>
          <p className="section-title">{formatDayLabel(selectedDate)}</p>
          {loading && daySlots.length === 0 ? (
            <div className="loading">
              <span className="spinner"></span>
              Загрузка слотов...
            </div>
          ) : daySlots.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">⏰</div>
              <div className="empty-state-title">Нет свободных слотов</div>
              <div className="empty-state-text">
                На этот день все слоты заняты. Выберите другой день.
              </div>
            </div>
          ) : (
            <div className="card">
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                {daySlots.map((t) => (
                  <button
                    key={t}
                    type="button"
                    className="btn btn-small"
                    style={{ flex: "1 1 calc(33.333% - 6px)", minWidth: 80 }}
                    onClick={() => {
                      haptic.selection();
                      setSelectedTime(t);
                      setStep("form");
                    }}
                  >
                    {t}
                  </button>
                ))}
              </div>
            </div>
          )}
          <button type="button" className="btn btn-destructive" onClick={goBack}>
            ← Другой день
          </button>
        </>
      )}

      {/* Шаг: форма */}
      {step === "form" && selectedDate && selectedTime && (
        <form onSubmit={handleSubmitForm}>
          <div className="card" style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 15, color: "var(--tg-hint)", marginBottom: 8 }}>
              Выбранное время
            </div>
            <div style={{ fontSize: 18, fontWeight: 600, color: "var(--tg-text)" }}>
              {formatDayLabel(selectedDate)} в {selectedTime}
            </div>
          </div>

          <p className="section-title">Ваши данные</p>
          <div className="group">
            <div className="group-item">
              <label className="label">Имя</label>
              <input
                className="input"
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                placeholder="Как к вам обращаться"
                required
              />
            </div>
            <div className="group-item">
              <label className="label">Тема встречи</label>
              <input
                className="input"
                value={form.subject}
                onChange={(e) => setForm((f) => ({ ...f, subject: e.target.value }))}
                placeholder="О чём встреча"
                required
              />
            </div>
            <div className="group-item">
              <label className="label">Email</label>
              <input
                type="email"
                className="input"
                value={form.email}
                onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
                placeholder="email@example.com"
                required
              />
            </div>
            <div className="group-item">
              <label className="label">Описание (необязательно)</label>
              <input
                className="input"
                value={form.description}
                onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                placeholder="Дополнительная информация"
              />
            </div>
          </div>
          <button type="submit" className="btn" disabled={loading} style={{ marginTop: 16 }}>
            {loading ? (
              <>
                <span className="spinner" style={{ marginRight: 8 }}></span>
                Отправка...
              </>
            ) : (
              "Отправить заявку"
            )}
          </button>
          <button type="button" className="btn btn-destructive" style={{ marginTop: 12 }} onClick={goBack}>
            ← Другое время
          </button>
        </form>
      )}

      {/* Успех */}
      {step === "success" && (
        <>
          <div className="success-message" style={{ marginTop: 24, textAlign: "center", padding: 24 }}>
            <div style={{ fontSize: 48, marginBottom: 16 }}>✓</div>
            <div style={{ fontSize: 18, fontWeight: 600, marginBottom: 8 }}>Заявка отправлена!</div>
            <div style={{ fontSize: 15 }}>
              {meetingId != null && `Номер заявки: #${meetingId}. `}
              Мы отправим уведомление после подтверждения встречи.
            </div>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 12, marginTop: 24 }}>
            <Link to="/my" style={{ textDecoration: "none" }}>
              <button type="button" className="btn btn-secondary">
                Мои заявки
              </button>
            </Link>
            <Link to="/" style={{ textDecoration: "none" }}>
              <button type="button" className="btn">
                На главную
              </button>
            </Link>
          </div>
        </>
      )}

      {/* Кнопка «назад» между шагами (кроме duration и success) */}
      {step === "week" && weekData && (
        <button type="button" className="btn btn-destructive" style={{ marginTop: 16 }} onClick={() => setStep("duration")}>
          ← Другая длительность
        </button>
      )}
    </div>
  );
}
