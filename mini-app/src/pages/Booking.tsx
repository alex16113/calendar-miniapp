import { useState, useEffect } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, type WeekDay } from "../api";

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
        setMeetingId(res.meeting_id);
        setStep("success");
      })
      .catch((e) => setError(e.message || "Ошибка отправки"))
      .finally(() => setLoading(false));
  };

  const daysWithSlots = weekData?.days.filter((d) => d.has_slots) ?? [];

  return (
    <div>
      <h1>Запрос встречи</h1>
      {step !== "success" && (
        <Link to="/" style={{ display: "block", marginBottom: 16, color: "var(--tg-button)", fontSize: 15 }}>← Назад</Link>
      )}

      {error && (
        <p style={{ color: "var(--destructive)", fontSize: 14, marginBottom: 12 }}>{error}</p>
      )}

      {/* Шаг: длительность */}
      {step === "duration" && (
        <>
          <p className="section-title">Длительность</p>
          <div className="group" style={{ padding: 12 }}>
            {DURATIONS.map((m) => (
              <button
                key={m}
                type="button"
                className="btn"
                style={{ marginBottom: 8 }}
                onClick={() => {
                  setDuration(m);
                  setWeekOffset(0);
                  setWeekData(null);
                  setStep("week");
                }}
              >
                {m} мин
              </button>
            ))}
          </div>
        </>
      )}

      {/* Шаг: выбор недели и дня */}
      {step === "week" && (
        <>
          <p className="section-title" style={{ textAlign: "center" }}>
            Неделя {getWeekRangeLabel(weekOffset)}
          </p>
          {loading && !weekData ? (
            <p style={{ color: "var(--tg-hint)" }}>Загрузка…</p>
          ) : (
            <div className="group" style={{ padding: 12 }}>
              {daysWithSlots.length === 0 ? (
                <p style={{ color: "var(--tg-text)", fontSize: 15, fontWeight: 500, margin: 0, textAlign: "center" }}>
                  Нет свободных дней на эту неделю
                </p>
              ) : (
                daysWithSlots.map((d) => (
                  <button
                    key={d.date}
                    type="button"
                    className="btn"
                    style={{ marginBottom: 8 }}
                    onClick={() => {
                      setSelectedDate(d.date);
                      setStep("time");
                      setDaySlots([]);
                    }}
                  >
                    {formatDayLabel(d.date)}
                  </button>
                ))
              )}
            </div>
          )}
          <Link
            to={`/book?w=${weekOffset + 1}`}
            style={{ display: "block", marginTop: 12, textDecoration: "none" }}
          >
            <span className="btn" style={{ display: "block", textAlign: "center" }}>
              Следующая неделя →
            </span>
          </Link>
        </>
      )}

      {/* Шаг: выбор времени */}
      {step === "time" && selectedDate && (
        <>
          <p className="section-title">{formatDayLabel(selectedDate)}</p>
          {loading && daySlots.length === 0 ? (
            <p style={{ color: "var(--tg-hint)" }}>Загрузка…</p>
          ) : (
            <div className="group" style={{ padding: 12, display: "flex", flexWrap: "wrap", gap: 8 }}>
              {daySlots.map((t) => (
                <button
                  key={t}
                  type="button"
                  className="btn"
                  style={{ flex: "1 1 80px", minWidth: 80 }}
                  onClick={() => {
                    setSelectedTime(t);
                    setStep("form");
                  }}
                >
                  {t}
                </button>
              ))}
            </div>
          )}
          <button type="button" className="btn" style={{ background: "transparent", color: "var(--tg-button)" }} onClick={goBack}>
            ← Другой день
          </button>
        </>
      )}

      {/* Шаг: форма */}
      {step === "form" && selectedDate && selectedTime && (
        <form onSubmit={handleSubmitForm}>
          <p className="section-title">Ваши данные</p>
          <div className="group" style={{ padding: 16 }}>
            <label className="label">Имя</label>
            <input
              className="input"
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              placeholder="Как к вам обращаться"
              required
              style={{ marginBottom: 12 }}
            />
            <label className="label">Тема встречи</label>
            <input
              className="input"
              value={form.subject}
              onChange={(e) => setForm((f) => ({ ...f, subject: e.target.value }))}
              placeholder="Кратко"
              required
              style={{ marginBottom: 12 }}
            />
            <label className="label">Описание (необязательно)</label>
            <input
              className="input"
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              placeholder="Ссылка на Zoom/Meet и т.п."
              style={{ marginBottom: 12 }}
            />
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
          <button type="submit" className="btn" disabled={loading}>
            {loading ? "Отправка…" : "Отправить"}
          </button>
          <button type="button" className="btn btn-destructive" style={{ marginTop: 8 }} onClick={goBack}>
            ← Другое время
          </button>
        </form>
      )}

      {/* Успех */}
      {step === "success" && (
        <>
          <p style={{ color: "var(--tg-text)", marginBottom: 16 }}>
            Заявка {meetingId != null ? `#${meetingId} ` : ""}отправлена. Мы свяжемся с вами после подтверждения.
          </p>
          <div className="nav-links">
            <Link to="/my">Мои заявки</Link>
            <Link to="/">На главную</Link>
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
