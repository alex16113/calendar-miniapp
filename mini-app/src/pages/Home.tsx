import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";

export default function Home() {
  const [isAdmin, setIsAdmin] = useState<boolean | null>(null);
  const [initDataMissing, setInitDataMissing] = useState(false);

  useEffect(() => {
    // Проверяем наличие Telegram WebApp и initData
    const tw = (window as any).Telegram?.WebApp;
    if (!tw || !tw.initData) {
      console.warn("[Home] initData missing - app opened outside Telegram or Menu Button not configured");
      setInitDataMissing(true);
      return;
    }

    let cancelled = false;
    api.admin
      .getSettings()
      .then(() => {
        if (!cancelled) setIsAdmin(true);
      })
      .catch(() => {
        if (!cancelled) setIsAdmin(false);
      });
    return () => { cancelled = true; };
  }, []);

  // Если initData отсутствует - показываем инструкцию
  if (initDataMissing) {
    return (
      <div className="empty-state">
        <div className="empty-state-icon">⚠️</div>
        <div className="empty-state-title">Приложение нужно открыть через Telegram</div>
        <div className="empty-state-text">
          Это приложение работает только при запуске из Telegram-бота.
        </div>
        <div className="card" style={{ marginTop: 24, textAlign: "left" }}>
          <div style={{ fontWeight: 600, marginBottom: 12, fontSize: 15 }}>Как открыть правильно:</div>
          <ol style={{ paddingLeft: 20, margin: 0, fontSize: 14, lineHeight: 1.6 }}>
            <li style={{ marginBottom: 8 }}>Найди бота <strong>@google_calendar_booking1_bot</strong> в Telegram</li>
            <li style={{ marginBottom: 8 }}>Нажми кнопку <strong>"Открыть приложение"</strong> внизу</li>
            <li>Если кнопки нет — напиши <code>/start</code></li>
          </ol>
        </div>
      </div>
    );
  }

  return (
    <div>
      <h1>Запись встречи</h1>
      <p style={{ color: "var(--tg-hint)", fontSize: 15, marginBottom: 24, lineHeight: 1.5 }}>
        Выберите действие ниже. Бронирование занимает меньше минуты.
      </p>

      <div className="card">
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 18, fontWeight: 600, marginBottom: 6, letterSpacing: "-0.3px" }}>
            Новая встреча
          </div>
          <div style={{ fontSize: 14, color: "var(--tg-hint)", lineHeight: 1.5 }}>
            Выберите удобное время в календаре и заполните краткую форму.
          </div>
        </div>
        <Link to="/book" style={{ textDecoration: "none" }}>
          <button type="button" className="btn">
            Записаться
          </button>
        </Link>
      </div>

      <div className="card">
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 18, fontWeight: 600, marginBottom: 6, letterSpacing: "-0.3px" }}>
            Мои заявки
          </div>
          <div style={{ fontSize: 14, color: "var(--tg-hint)", lineHeight: 1.5 }}>
            Просмотр подтверждённых и ожидающих встреч.
          </div>
        </div>
        <Link to="/my" style={{ textDecoration: "none" }}>
          <button type="button" className="btn btn-secondary">
            Открыть
          </button>
        </Link>
      </div>

      {isAdmin === true && (
        <div className="card">
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 18, fontWeight: 600, marginBottom: 6, letterSpacing: "-0.3px" }}>
              Админ-панель
            </div>
            <div style={{ fontSize: 14, color: "var(--tg-hint)", lineHeight: 1.5 }}>
              Управление заявками, настройки и модерация.
            </div>
          </div>
          <Link to="/admin" style={{ textDecoration: "none" }}>
            <button type="button" className="btn btn-secondary">
              Открыть
            </button>
          </Link>
        </div>
      )}
    </div>
  );
}
