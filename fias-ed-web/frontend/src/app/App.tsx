import { BrowserRouter, Navigate, Route, Routes } from "react-router";
import { Home } from "../pages/Home";
import { TrocarSenha } from "../pages/TrocarSenha";
import { AulaPage } from "../pages/AulaPage";
import { Dashboard } from "../pages/Dashboard";
import { NovaAula } from "../pages/NovaAula";
import { AuthProvider } from "./AuthContext";
import { Layout } from "./Layout";
import { RequireAuth } from "./RequireAuth";

export function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/trocar-senha" element={<RequireAuth allowPasswordChange><TrocarSenha /></RequireAuth>} />
          <Route element={<RequireAuth><Layout /></RequireAuth>}>
            <Route path="/aulas" element={<Dashboard />} />
            <Route path="/aulas/nova" element={<NovaAula />} />
            <Route path="/aulas/:id" element={<AulaPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
