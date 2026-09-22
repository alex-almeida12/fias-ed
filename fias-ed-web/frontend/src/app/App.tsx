import { BrowserRouter, Navigate, Route, Routes } from "react-router";
import { Home } from "../pages/Home";
import { TrocarSenha } from "../pages/TrocarSenha";
import { AulaPage } from "../pages/AulaPage";
import { Dashboard } from "../pages/Dashboard";
import { NovaAula } from "../pages/NovaAula";
import { AdminAulas } from "../pages/admin/AdminAulas";
import { Contas } from "../pages/admin/Contas";
import { Escolas } from "../pages/admin/Escolas";
import { AuthProvider } from "./AuthContext";
import { Layout } from "./Layout";
import { RequireAdmin, RequireAuth } from "./RequireAuth";

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
            <Route path="/admin/contas" element={<RequireAdmin><Contas /></RequireAdmin>} />
            <Route path="/admin/aulas" element={<RequireAdmin><AdminAulas /></RequireAdmin>} />
            <Route path="/admin/escolas" element={<RequireAdmin><Escolas /></RequireAdmin>} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
