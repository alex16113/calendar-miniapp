import { useState, useEffect } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, type WeekDay } from "../api";
import { haptic } from "../utils/haptic";
import { getTelegramDisplayName } from "../utils/telegramUser";

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
  const [prefilled, setPrefilled] = useState(false);

  // Автозаполнение при монтировании: имя из Telegram, email из /my/profile
  useEffect(() => {
    if (prefilled) return;
    const tgName = getTelegramDisplayName();
    api
      .getMyProfile()
      .then((profile) => {
        setForm((f) => ({
          ...f,
          name: (f.name || profile.user_name || tgName || "").trim(),
          email: (f.email || profile.user_email || "").trim(),
        }));
        setPrefilled(true);
      })
      .catch(() => {
        if (tgName) setForm((f) => ({ ...f, name: (f.name || tgName).trim() }));
        setPrefilled(true);
      });
  }, [prefilled]);

  // Повторная попытка при входе на шаг «форма» — если к этому моменту появились initData/профиль
  useEffect(() => {
    if (step !== "form") return;
    const tgName = getTelegramDisplayName();
    const needName = !form.name.trim();
    const needEmail = !form.email.trim();
    if (!needName && !needEmail) return;
    api.getMyProfile().then(
      (profile) => {
        setForm((f) => ({
          ...f,
          name: needName ? (profile.user_name || tgName || f.name || "").trim() : f.name,
          email: needEmail ? (profile.user_email || f.email || "").trim() : f.email,
        }));
      },
      () => {
        if (needName && tgName) setForm((f) => ({ ...f, name: tgName.trim() }));
      }
    );
  }, [step]);

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
    <>
      <div className="mesh-gradient-bg" />
      <div className="page">
        {step !== "success" && (
          <Link to="/" className="page-back">← Назад</Link>
        )}
        <h1 className="page-title">Новая встреча</h1>

        {error && <div className="glass-error">{error}</div>}

        {/* Шаг: длительность */}
        {step === "duration" && (
          <>
            <p className="page-section-label">Выберите длительность планируемой встречи</p>
            <div className="glass-panel">
              {DURATIONS.map((m) => (
                <button
                  key={m}
                  type="button"
                  className="glass-btn"
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
              ))}
            </div>
          </>
        )}

        {/* Шаг: выбор недели и дня */}
        {step === "week" && (
          <>
            <div className="week-badge">
              <span className="week-badge-icon">🗓️</span>
              <span className="week-badge-text">{getWeekRangeLabel(weekOffset)}</span>
            </div>
            {loading && !weekData ? (
              <div className="glass-loading">
                <span className="spinner"></span>
                Загрузка дней...
              </div>
            ) : daysWithSlots.length === 0 ? (
              <div className="glass-empty">
                <div className="glass-empty-icon">🗓️</div>
                <div className="glass-empty-title">Нет свободных дней</div>
                <div className="glass-empty-text">
                  Попробуйте следующую неделю
                </div>
              </div>
            ) : (
              <div className="glass-panel">
                {daysWithSlots.map((d) => (
                  <button
                    key={d.date}
                    type="button"
                    className="glass-btn"
                    onClick={() => {
                      haptic.selection();
                      setSelectedDate(d.date);
                      setStep("time");
                      setDaySlots([]);
                    }}
                  >
                    {formatDayLabel(d.date)}
                  </button>
                ))}
              </div>
            )}
            <Link to={`/book?w=${weekOffset + 1}`} className="glass-btn glass-btn-accent" style={{ marginTop: 8 }}>
              Следующая неделя →
            </Link>
            <button type="button" className="glass-btn glass-btn-muted" onClick={() => setStep("duration")} style={{ marginTop: 8 }}>
              ← Изменить длительность
            </button>
          </>
        )}

        {/* Шаг: выбор времени */}
        {step === "time" && selectedDate && (
          <>
            <div className="week-badge">
              <span className="week-badge-icon">🕐</span>
              <span className="week-badge-text">{formatDayLabel(selectedDate)}</span>
            </div>
            {loading && daySlots.length === 0 ? (
              <div className="glass-loading">
                <span className="spinner"></span>
                Загрузка слотов...
              </div>
            ) : daySlots.length === 0 ? (
              <div className="glass-empty">
                <div className="glass-empty-icon">⏰</div>
                <div className="glass-empty-title">Нет свободных слотов</div>
                <div className="glass-empty-text">Выберите другой день</div>
              </div>
            ) : (
              <div className="glass-panel">
                <div className="time-grid">
                  {daySlots.map((t) => (
                    <button
                      key={t}
                      type="button"
                      className="time-slot"
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
            <button type="button" className="glass-btn glass-btn-muted" onClick={goBack} style={{ marginTop: 8 }}>
              ← Выбрать другой день
            </button>
          </>
        )}

        {/* Шаг: форма */}
        {step === "form" && selectedDate && selectedTime && (
          <form onSubmit={handleSubmitForm}>
            <div className="week-badge" style={{ marginBottom: 20 }}>
              <span className="week-badge-icon">⏰</span>
              <span className="week-badge-text">{formatDayLabel(selectedDate)}, {selectedTime}</span>
            </div>

            <p className="page-section-label">Ваши данные</p>
            <div className="glass-panel" style={{ padding: 0 }}>
              <div className="glass-form-group">
                <label className="glass-form-label">Имя</label>
                <input
                  className="glass-input"
                  value={form.name}
                  onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                  placeholder="Как к вам обращаться"
                  required
                />
              </div>
              <div className="glass-form-group">
                <label className="glass-form-label">Тема встречи</label>
                <input
                  className="glass-input"
                  value={form.subject}
                  onChange={(e) => setForm((f) => ({ ...f, subject: e.target.value }))}
                  placeholder="О чём встреча"
                  required
                />
              </div>
              <div className="glass-form-group">
                <label className="glass-form-label">Email</label>
                <input
                  type="email"
                  className="glass-input"
                  value={form.email}
                  onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
                  placeholder="email@example.com"
                  required
                />
              </div>
              <div className="glass-form-group">
                <label className="glass-form-label">Описание</label>
                <input
                  className="glass-input"
                  value={form.description}
                  onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                  placeholder="Необязательно"
                />
              </div>
            </div>

            <button type="submit" className="glass-btn glass-btn-accent" disabled={loading} style={{ marginTop: 16 }}>
              {loading ? "Отправка..." : "Отправить заявку"}
            </button>
            <button type="button" className="glass-btn glass-btn-muted" style={{ marginTop: 8 }} onClick={goBack}>
              ← Выбрать другое время
            </button>
          </form>
        )}

        {/* Успех */}
        {step === "success" && (
          <>
            <div className="glass-success">
              <div className="glass-success-icon">✓</div>
              <div className="glass-success-title">Заявка отправлена!</div>
              <div className="glass-success-text">
                {meetingId != null && <>Номер заявки: #{meetingId}.<br /></>}
                Мы уведомим вас после подтверждения.
              </div>
            </div>
            <Link to="/my" className="glass-btn" style={{ marginBottom: 12 }}>
              Мои заявки
            </Link>
            <Link to="/" className="glass-btn glass-btn-accent">
              На главную
            </Link>
          </>
        )}
      </div>
    </>
  );
}
