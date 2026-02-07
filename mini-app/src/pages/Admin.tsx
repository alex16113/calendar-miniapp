import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { api, type AdminPendingItem } from "../api";
import { haptic } from "../utils/haptic";

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
    haptic.medium();
    api.admin
      .confirmMeeting(id)
      .then(() => {
        haptic.success();
        removeFromList(id);
      })
      .catch((e) => {
        haptic.error();
        alert(e.message || "Ошибка");
      });
  };

  const handleReject = (id: number) => {
    if (!confirm("Отклонить заявку?")) return;
    haptic.medium();
    api.admin
      .rejectMeeting(id)
      .then(() => {
        haptic.success();
        removeFromList(id);
      })
      .catch((e) => {
        haptic.error();
        alert(e.message || "Ошибка");
      });
  };

  const handleBan = (id: number) => {
    if (!confirm("Отклонить и добавить пользователя в бан?")) return;
    haptic.medium();
    api.admin
      .banMeeting(id)
      .then(() => {
        haptic.success();
        removeFromList(id);
      })
      .catch((e) => {
        haptic.error();
        alert(e.message || "Ошибка");
      });
  };

  if (forbidden) {
    return (
      <div>
        <h1>Админ-панель</h1>
        <div className="empty-state">
          <div className="empty-state-icon">🔒</div>
          <div className="empty-state-title">Доступ запрещён</div>
          <div className="empty-state-text">
            Эта страница доступна только администратору. Откройте приложение из аккаунта владельца.
          </div>
        </div>
        <Link to="/" style={{ textDecoration: "none", marginTop: 24 }}>
          <button type="button" className="btn">
            На главную
          </button>
        </Link>
      </div>
    );
  }

  return (
    <div>
      <h1>Админ-панель</h1>
      <Link to="/" className="back-link">
        ← Назад
      </Link>

      {error && <div className="error-message">{error}</div>}

      <p className="section-title">Ожидающие заявки</p>
      
      {loading && pending.length === 0 ? (
        <div className="loading">
          <span className="spinner"></span>
          Загрузка заявок...
        </div>
      ) : pending.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">✓</div>
          <div className="empty-state-title">Нет заявок в ожидании</div>
          <div className="empty-state-text">
            Все заявки обработаны. Новые заявки появятся здесь автоматически.
          </div>
        </div>
      ) : (
        <>
          <div className="group">
            {pending.map((m, idx) => (
              <div
                key={m.id}
                className="group-item"
                style={{ borderBottom: idx === pending.length - 1 ? "none" : undefined }}
              >
                <div style={{ marginBottom: 12 }}>
                  <div style={{ fontWeight: 600, fontSize: 16, marginBottom: 4 }}>
                    {m.start_local}
                  </div>
                  <div style={{ fontSize: 14, color: "var(--tg-hint)" }}>
                    {m.user_name || "Неизвестно"} · {m.subject || "Без темы"}
                  </div>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                  <button 
                    type="button" 
                    className="btn btn-small" 
                    onClick={() => handleConfirm(m.id)}
                  >
                    ✓ Подтвердить
                  </button>
                  <button
                    type="button"
                    className="btn btn-small btn-destructive"
                    onClick={() => handleReject(m.id)}
                  >
                    ✕ Отклонить
                  </button>
                  <button
                    type="button"
                    className="btn btn-small btn-destructive"
                    style={{ gridColumn: "1 / -1" }}
                    onClick={() => handleBan(m.id)}
                  >
                    🚫 Отклонить и заблокировать
                  </button>
                </div>
              </div>
            ))}
          </div>

          {total > limit && (
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
                Страница {page + 1} из {Math.ceil(total / limit)}
              </span>
              <button
                type="button"
                className="btn btn-small"
                style={{ width: "auto", paddingLeft: 24, paddingRight: 24 }}
                disabled={page >= Math.ceil(total / limit) - 1}
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
