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
    <>
      <div className="mesh-gradient-bg" />
      <div className="page">
        <Link to="/" className="page-back">← Назад</Link>
        <h1 className="page-title">Мои заявки</h1>

        {loading && !data && (
          <div className="glass-loading">
            <span className="spinner"></span>
            Загрузка заявок...
          </div>
        )}

        {error && <div className="glass-error">{error}</div>}

        {!loading && !error && list.length === 0 && (
          <div className="glass-empty">
            <div className="glass-empty-icon">📋</div>
            <div className="glass-empty-title">Нет заявок</div>
            <div className="glass-empty-text">
              У вас пока нет записей. Создайте новую, чтобы забронировать время.
            </div>
            <Link to="/book" className="glass-btn glass-btn-accent" style={{ marginTop: 24 }}>
              Создать заявку
            </Link>
          </div>
        )}

        {list.length > 0 && (
          <>
            {list.map((m, idx) => (
              <div
                key={m.id}
                className={`meeting-card ${idx % 2 === 0 ? "meeting-card-even" : "meeting-card-odd"}`}
              >
                <div className="meeting-card-header">
                  <div className="meeting-card-date">
                    <span className="meeting-card-date-icon">🗓️</span>
                    <span>{m.start_local}</span>
                  </div>
                  <span className={`meeting-status meeting-status-${m.status}`}>
                    {m.status === "pending" ? "Ожидание" : "Подтверждено"}
                  </span>
                </div>

                <div className="meeting-card-subject">
                  {m.subject || "Без темы"}
                </div>

                {m.status === "pending" && (
                  <button
                    type="button"
                    className="meeting-card-action meeting-card-action-cancel"
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
                    className="meeting-card-action meeting-card-action-calendar"
                  >
                    📎 Открыть в Google Calendar
                  </a>
                )}
              </div>
            ))}

            {totalPages > 1 && (
              <div style={{ display: "flex", gap: 12, marginTop: 20, alignItems: "center", justifyContent: "center" }}>
                <button
                  type="button"
                  className="glass-btn glass-btn-muted"
                  style={{ width: "auto", padding: "10px 24px", fontSize: 14 }}
                  disabled={page === 0}
                  onClick={() => setPage((p) => p - 1)}
                >
                  ←
                </button>
                <span style={{ color: "rgba(255,255,255,0.5)", fontSize: 14 }}>
                  {page + 1} / {totalPages}
                </span>
                <button
                  type="button"
                  className="glass-btn glass-btn-muted"
                  style={{ width: "auto", padding: "10px 24px", fontSize: 14 }}
                  disabled={page >= totalPages - 1}
                  onClick={() => setPage((p) => p + 1)}
                >
                  →
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </>
  );
}
