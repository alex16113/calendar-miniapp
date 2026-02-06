import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type MyMeetingItem } from "../api";

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
    api
      .cancelMeeting(id)
      .then(() => {
        setData((prev) =>
          prev
            ? { ...prev, items: prev.items.filter((m) => m.id !== id), total: prev.total - 1 }
            : null
        );
      })
      .catch((e) => alert(e.message));
  };

  if (loading && !data) return <p>Загрузка…</p>;
  if (error) return <p style={{ color: "var(--destructive)" }}>{error}</p>;

  const list = data?.items ?? [];
  const totalPages = data?.total_pages ?? 1;

  return (
    <div>
      <h1>Мои заявки</h1>
      <Link to="/" style={{ display: "block", marginBottom: 16 }}>← Назад</Link>
      {list.length === 0 ? (
        <p style={{ color: "var(--tg-hint)" }}>Нет заявок.</p>
      ) : (
        <div className="group" style={{ padding: 12 }}>
          {list.map((m) => (
            <div
              key={m.id}
              style={{
                padding: "12px 0",
                borderBottom: "1px solid rgba(0,0,0,0.06)",
              }}
            >
              <div style={{ fontWeight: 500 }}>{m.start_local}</div>
              <div style={{ fontSize: 14, color: "var(--tg-hint)" }}>
                {m.subject || "—"} · {m.status === "pending" ? "⏳ ожидание" : "✅ подтверждено"}
              </div>
              {m.status === "pending" && (
                <button
                  type="button"
                  className="btn btn-destructive"
                  style={{ marginTop: 8 }}
                  onClick={() => cancel(m.id)}
                >
                  Отменить
                </button>
              )}
              {m.status === "confirmed" && m.google_event_html_link && (
                <a
                  href={m.google_event_html_link}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ display: "inline-block", marginTop: 8, color: "var(--tg-button)" }}
                >
                  Открыть в календаре
                </a>
              )}
            </div>
          ))}
        </div>
      )}
      {totalPages > 1 && (
        <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
          <button
            type="button"
            className="btn"
            disabled={page === 0}
            onClick={() => setPage((p) => p - 1)}
          >
            ←
          </button>
          <span style={{ alignSelf: "center" }}>
            {page + 1} / {totalPages}
          </span>
          <button
            type="button"
            className="btn"
            disabled={page >= totalPages - 1}
            onClick={() => setPage((p) => p + 1)}
          >
            →
          </button>
        </div>
      )}
    </div>
  );
}
