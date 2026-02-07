import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type MyMeetingItem } from "../api";
import { haptic } from "../utils/haptic";

export default function MyMeetings() {
  const [data, setData] = useState<{ items: MyMeetingItem[]; total: number; total_pages: number } | null>(null);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .getMyMeetings(page, 10)
      .then((res) => {
        if (!cancelled) setData(res);
      })
      .catch((e) => {
        if (!cancelled) setError(e.message || "Ошибка загрузки");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [page]);

  const cancel = (id: number) => {
    if (!confirm("Отменить заявку?")) return;
    haptic.medium();
    api
      .cancelMeeting(id)
      .then(() => {
        haptic.success();
        setData((prev) =>
          prev
            ? { ...prev, items: prev.items.filter((m) => m.id !== id), total: prev.total - 1 }
            : null
        );
      })
      .catch((e) => {
        haptic.error();
        alert(e.message);
      });
  };

  const list = data?.items ?? [];
  const totalPages = data?.total_pages ?? 1;

  return (
    <div>
      <h1>Мои заявки</h1>
      <Link to="/" className="back-link">
        ← Назад
      </Link>

      {loading && !data && (
        <div className="loading">
          <span className="spinner"></span>
          Загрузка заявок...
        </div>
      )}

      {error && (
        <div className="error-message">{error}</div>
      )}

      {!loading && !error && list.length === 0 && (
        <div className="empty-state">
          <div className="empty-state-icon">📋</div>
          <div className="empty-state-title">Нет заявок</div>
          <div className="empty-state-text">
            У вас пока нет заявок на встречи. Создайте новую, чтобы забронировать время.
          </div>
          <Link to="/book" style={{ textDecoration: "none", marginTop: 24 }}>
            <button type="button" className="btn">
              Создать заявку
            </button>
          </Link>
        </div>
      )}

      {list.length > 0 && (
        <>
          <p className="section-title">Все заявки</p>
          <div className="group">
            {list.map((m, idx) => (
              <div
                key={m.id}
                className="group-item"
                style={{ borderBottom: idx === list.length - 1 ? "none" : undefined }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
                  <div style={{ fontWeight: 600, fontSize: 16 }}>{m.start_local}</div>
                  <span className={`status-badge status-${m.status}`}>
                    {m.status === "pending" ? "Ожидание" : "Подтверждено"}
                  </span>
                </div>
                <div style={{ fontSize: 14, color: "var(--tg-hint)", marginBottom: 12 }}>
                  {m.subject || "Без темы"}
                </div>
                {m.status === "pending" && (
                  <button
                    type="button"
                    className="btn btn-destructive btn-small"
                    onClick={() => cancel(m.id)}
                  >
                    Отменить заявку
                  </button>
                )}
                {m.status === "confirmed" && m.google_event_html_link && (
                  <a
                    href={m.google_event_html_link}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ display: "inline-block", color: "var(--tg-button)", fontSize: 14, fontWeight: 500 }}
                  >
                    Открыть в Google Calendar →
                  </a>
                )}
              </div>
            ))}
          </div>

          {totalPages > 1 && (
            <div style={{ display: "flex", gap: 12, marginTop: 16, alignItems: "center", justifyContent: "center" }}>
              <button
                type="button"
                className="btn btn-small"
                style={{ width: "auto", paddingLeft: 24, paddingRight: 24 }}
                disabled={page === 0}
                onClick={() => setPage((p) => p - 1)}
              >
                ← Назад
              </button>
              <span style={{ color: "var(--tg-hint)", fontSize: 14 }}>
                Страница {page + 1} из {totalPages}
              </span>
              <button
                type="button"
                className="btn btn-small"
                style={{ width: "auto", paddingLeft: 24, paddingRight: 24 }}
                disabled={page >= totalPages - 1}
                onClick={() => setPage((p) => p + 1)}
              >
                Вперёд →
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
