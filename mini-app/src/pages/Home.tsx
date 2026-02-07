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
      <div style={{ padding: 20, textAlign: "center" }}>
        <h2 style={{ fontSize: 18, marginBottom: 16 }}>⚠️ Приложение нужно открыть через Telegram</h2>
        <p style={{ color: "var(--tg-theme-hint-color)", fontSize: 14, marginBottom: 12 }}>
          Это приложение работает только при запуске из Telegram-бота.
        </p>
        <div style={{ textAlign: "left", maxWidth: 400, margin: "0 auto", fontSize: 14, color: "var(--tg-theme-hint-color)" }}>
          <p style={{ marginBottom: 8 }}><strong>Как открыть правильно:</strong></p>
          <ol style={{ paddingLeft: 20 }}>
            <li style={{ marginBottom: 8 }}>Найди бота <strong>@google_calendar_booking1_bot</strong> в Telegram</li>
            <li style={{ marginBottom: 8 }}>Нажми кнопку <strong>"Открыть приложение"</strong> внизу (рядом с полем ввода)</li>
            <li>Если кнопки нет — напиши <code>/start</code></li>
          </ol>
        </div>
      </div>
    );
  }

  return (
    <div>
      <h1 style={{ textAlign: "center" }}>Запись. Календарь Алексея.</h1>
      <p style={{ color: "var(--tg-hint)", fontSize: 15, marginBottom: 16, textAlign: "center" }}>
        Быстрый способ назначить встречу.
      </p>

      <div className="group" style={{ padding: 16 }}>
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 4 }}>
            Новый запрос
          </div>
          <div style={{ fontSize: 14, color: "var(--tg-hint)" }}>
            Выбери длительность, дату и время — остальное подставится автоматически.
          </div>
        </div>
        <Link to="/book">
          <button type="button" className="btn">
            Записаться на встречу
          </button>
        </Link>
      </div>

      <div className="group" style={{ padding: 16 }}>
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 4 }}>
            Мои заявки
          </div>
          <div style={{ fontSize: 14, color: "var(--tg-hint)" }}>
            Подтверждённые и ожидающие встречи.
          </div>
        </div>
        <Link to="/my">
          <button type="button" className="btn">
            Открыть список
          </button>
        </Link>
      </div>

      {isAdmin === true && (
        <div className="group" style={{ padding: 16 }}>
          <div style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 4 }}>
              Админка
            </div>
            <div style={{ fontSize: 14, color: "var(--tg-hint)" }}>
              Ожидающие заявки, настройки, рассылка.
            </div>
          </div>
          <Link to="/admin">
            <button type="button" className="btn" style={{ background: "transparent", color: "var(--tg-button)" }}>
              Открыть админку
            </button>
          </Link>
        </div>
      )}
    </div>
  );
}
