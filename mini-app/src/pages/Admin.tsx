import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { api, type AdminPendingItem } from "../api";

export default function Admin() {
  const [pending, setPending] = useState<AdminPendingItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);
  const limit = 10;

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setForbidden(false);
    api.admin
      .getPending(page, limit)
      .then((res) => {
        if (!cancelled) {
          setPending(res.items);
          setTotal(res.total);
        }
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
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [page]);

  const removeFromList = (id: number) => {
    setPending((prev) => prev.filter((m) => m.id !== id));
    setTotal((t) => Math.max(0, t - 1));
  };

  const handleConfirm = (id: number) => {
    api.admin
      .confirmMeeting(id)
      .then(() => removeFromList(id))
      .catch((e) => alert(e.message || "Ошибка"));
  };

  const handleReject = (id: number) => {
    if (!confirm("Отклонить заявку?")) return;
    api.admin
      .rejectMeeting(id)
      .then(() => removeFromList(id))
      .catch((e) => alert(e.message || "Ошибка"));
  };

  const handleBan = (id: number) => {
    if (!confirm("Отклонить и добавить пользователя в бан?")) return;
    api.admin
      .banMeeting(id)
      .then(() => removeFromList(id))
      .catch((e) => alert(e.message || "Ошибка"));
  };

  if (forbidden) {
    return (
      <div>
        <h1>Админка</h1>
        <p style={{ color: "var(--tg-hint)" }}>Доступ только для администратора. Откройте приложение из аккаунта владельца.</p>
        <Link to="/" style={{ color: "var(--tg-button)", display: "block", marginTop: 16 }}>← На главную</Link>
      </div>
    );
  }

  return (
    <div>
      <h1>Админка</h1>
      <Link to="/" style={{ display: "block", marginBottom: 16, color: "var(--tg-button)", fontSize: 15 }}>← Назад</Link>

      {error && <p style={{ color: "var(--destructive)", marginBottom: 12 }}>{error}</p>}

      <p className="section-title">Ожидающие заявки</p>
      {loading && pending.length === 0 ? (
        <p style={{ color: "var(--tg-hint)" }}>Загрузка…</p>
      ) : pending.length === 0 ? (
        <div className="group" style={{ padding: 12 }}>
          <p style={{ color: "var(--tg-hint)", margin: 0 }}>Нет заявок в ожидании</p>
        </div>
      ) : (
        <div className="group" style={{ padding: 12 }}>
          {pending.map((m) => (
            <div
              key={m.id}
              style={{
                padding: "12px 0",
                borderBottom: "1px solid rgba(0,0,0,0.06)",
              }}
            >
              <div style={{ fontWeight: 500 }}>{m.start_local}</div>
              <div style={{ fontSize: 14, color: "var(--tg-hint)" }}>
                {m.user_name || "—"} · {m.subject || "—"}
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 8 }}>
                <button type="button" className="btn" style={{ flex: "1 1 80px" }} onClick={() => handleConfirm(m.id)}>
                  ✅ Подтвердить
                </button>
                <button
                  type="button"
                  className="btn btn-destructive"
                  style={{ flex: "1 1 80px" }}
                  onClick={() => handleReject(m.id)}
                >
                  ❌ Отклонить
                </button>
                <button
                  type="button"
                  className="btn btn-destructive"
                  style={{ flex: "1 1 80px" }}
                  onClick={() => handleBan(m.id)}
                >
                  🚫 В бан
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {total > limit && (
        <div style={{ display: "flex", gap: 8, marginTop: 16, justifyContent: "center" }}>
          <button type="button" className="btn" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
            ←
          </button>
          <span style={{ alignSelf: "center" }}>
            {page + 1} / {Math.ceil(total / limit)}
          </span>
          <button
            type="button"
            className="btn"
            disabled={page >= Math.ceil(total / limit) - 1}
            onClick={() => setPage((p) => p + 1)}
          >
            →
          </button>
        </div>
      )}
    </div>
  );
}
