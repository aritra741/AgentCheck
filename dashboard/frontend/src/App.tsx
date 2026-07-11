import { Route, Routes } from "react-router-dom";
import { DefineAgent } from "./pages/DefineAgent";

export default function App() {
  return (
    <>
      <header className="app-header">
        <div className="logo-container">
          <h1>AgentCheck</h1>
          <span className="version-badge">Demo</span>
        </div>
      </header>

      <main className="app-main">
        <Routes>
          <Route path="/" element={<DefineAgent />} />
          <Route path="/define" element={<DefineAgent />} />
          <Route path="*" element={<DefineAgent />} />
        </Routes>
      </main>
    </>
  );
}
