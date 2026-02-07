import { HashRouter, Routes, Route } from "react-router-dom";
import Home from "./pages/Home";
import Booking from "./pages/Booking";
import MyMeetings from "./pages/MyMeetings";
import Admin from "./pages/Admin";
import "./index.css";

console.log('[APP] App.tsx loaded');

function App() {
  console.log('[APP] App component rendering');
  
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
