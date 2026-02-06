import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";

export default function Home() {
  const [isAdmin, setIsAdmin] = useState<boolean | null>(null);

  useEffect(() => {
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
