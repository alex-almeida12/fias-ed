import { BrowserRouter, Navigate, Route, Routes } from "react-router";
import { Home } from "../pages/Home";
import { TrocarSenha } from "../pages/TrocarSenha";
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
            <Route path="/aulas" element={null} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
