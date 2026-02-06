import { useEffect } from "react";
import { HashRouter, Routes, Route } from "react-router-dom";
import Home from "./pages/Home";
import Booking from "./pages/Booking";
import MyMeetings from "./pages/MyMeetings";
import Admin from "./pages/Admin";
import "./index.css";

function App() {
  useEffect(() => {
    const tw = (window as unknown as { Telegram?: { WebApp?: { ready: () => void; expand?: () => void } } }).Telegram?.WebApp;
    tw?.ready?.();
    tw?.expand?.();
  }, []);

  return (
    <HashRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/book" element={<Booking />} />
        <Route path="/my" element={<MyMeetings />} />
        <Route path="/admin" element={<Admin />} />
      </Routes>
    </HashRouter>
  );
}

export default App;
