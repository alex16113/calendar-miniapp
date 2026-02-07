import { HashRouter, Routes, Route, Navigate } from "react-router-dom";
import Home from "./pages/Home";
import Booking from "./pages/Booking";
import MyMeetings from "./pages/MyMeetings";
import Admin from "./pages/Admin";
import "./index.css";

console.log('[APP] App.tsx loaded');

function App() {
  console.log('[APP] App component rendering');
  console.log('[APP] Current location:', window.location.href);
  console.log('[APP] Hash:', window.location.hash);
  
  return (
    <HashRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/book" element={<Booking />} />
        <Route path="/my" element={<MyMeetings />} />
        <Route path="/admin" element={<Admin />} />
        {/* Fallback: любой неизвестный путь → главная */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </HashRouter>
  );
}

export default App;
