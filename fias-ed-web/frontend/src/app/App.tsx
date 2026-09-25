import { BrowserRouter, Navigate, Route, Routes } from "react-router";
import { Acompanhamentos } from "../pages/Acompanhamentos";
import { Home } from "../pages/Home";
import { TrocarSenha } from "../pages/TrocarSenha";
import { AulaPage } from "../pages/AulaPage";
import { Dashboard } from "../pages/Dashboard";
import { EscolhaVoz } from "../pages/EscolhaVoz";
import { ImportarQTI } from "../pages/ImportarQTI";
import { NovaAula } from "../pages/NovaAula";
import { NovoCiclo } from "../pages/NovoCiclo";
import { PadroesInteracao } from "../pages/PadroesInteracao";
import { RelatorioAula } from "../pages/RelatorioAula";
import { RelatorioCiclo } from "../pages/RelatorioCiclo";
import { RevisaoTranscricao } from "../pages/RevisaoTranscricao";
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
            <Route path="/ciclos" element={<Acompanhamentos />} />
            <Route path="/ciclos/novo" element={<NovoCiclo />} />
            <Route path="/ciclos/:id/qti" element={<ImportarQTI />} />
            <Route path="/ciclos/:id/relatorio" element={<RelatorioCiclo />} />
            <Route path="/aulas/:id" element={<AulaPage />} />
            <Route path="/aulas/:id/vozes" element={<EscolhaVoz />} />
            <Route path="/aulas/:id/transcricao" element={<RevisaoTranscricao />} />
            <Route path="/aulas/:id/padroes" element={<PadroesInteracao />} />
            <Route path="/aulas/:id/relatorio" element={<RelatorioAula />} />
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
