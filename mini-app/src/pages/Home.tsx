import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { haptic } from "../utils/haptic";

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
    <>
      {/* Mesh Gradient Background */}
      <div className="mesh-gradient-bg" />
      
      <div>
        {/* Header */}
        <header className="home-header">
          <h1 className="home-title">Easy Meet</h1>
          <p className="home-subtitle">
            Назначайте встречи прямо в Telegram, выбирайте удобные слоты и получайте мгновенные уведомления о согласовании
          </p>
        </header>

        {/* Main Stack - Glass Cards */}
        <div style={{ paddingBottom: isAdmin ? 80 : 40 }}>
          <Link 
            to="/book" 
            className="glass-card"
            onClick={() => haptic.light()}
          >
            <div className="glass-card-content">
              <div className="glass-card-icon">🗓️</div>
              <div className="glass-card-text">
                <h2 className="glass-card-title">Назначить встречу</h2>
                <p className="glass-card-subtitle">Выбрать слот</p>
              </div>
            </div>
          </Link>

          <Link 
            to="/my" 
            className="glass-card"
            onClick={() => haptic.light()}
          >
            <div className="glass-card-content">
              <div className="glass-card-icon">📋</div>
              <div className="glass-card-text">
                <h2 className="glass-card-title">Мои записи</h2>
                <p className="glass-card-subtitle">Предстоящие встречи</p>
              </div>
            </div>
          </Link>
        </div>

        {/* Admin Footer */}
        {isAdmin === true && (
          <footer className="admin-footer">
            <Link to="/admin" className="admin-footer-link">
              <span>⚙️</span>
              <span>Пульт управления</span>
            </Link>
          </footer>
        )}
      </div>
    </>
  );
}
