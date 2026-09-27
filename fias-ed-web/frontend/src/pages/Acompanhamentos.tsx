import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router";
import { api, ApiError } from "../api/client";
import type { CicloNaLista, LinkQtiGerado } from "../api/types";
import { formatDate, localDateInput } from "../app/format";
import { Banner } from "../design/components/Banner";
import { Button } from "../design/components/Button";
import { Dialog } from "../design/components/Dialog";
import { EmptyState } from "../design/components/EmptyState";
import { TextField } from "../design/components/Field";

type LinkGerado = LinkQtiGerado & { cicloId: string };
type Revogando = { cicloId: string; linkId: string };

export function Acompanhamentos() {
  const [acompanhamentos, setAcompanhamentos] = useState<CicloNaLista[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [encerrando, setEncerrando] = useState<CicloNaLista | null>(null);

  // Estado só de memória, de propósito: o token só existe na resposta de POST .../qti/link,
  // nunca em GET /ciclos (nem o hash sai de lá). Guardá-lo em algo que sobreviva a um
  // recarregamento da tela faria o segredo sobreviver à sessão sem o servidor saber.
  const [gerandoPara, setGerandoPara] = useState<CicloNaLista | null>(null);
  const [nEstudantes, setNEstudantes] = useState("");
  const [dias, setDias] = useState("7");
  const [coletadoEm, setColetadoEm] = useState("");
  const [gerarErro, setGerarErro] = useState<string | null>(null);
  const [gerando, setGerando] = useState(false);
  const [linkGerado, setLinkGerado] = useState<LinkGerado | null>(null);

  const [revogando, setRevogando] = useState<Revogando | null>(null);

  // Reaproveitada após encerrar (Task 18): a resposta de POST /ciclos/{id}/encerrar não tem o
  // formato de Ciclo (traz turma_id/disciplina_id, não os objetos turma/disciplina) — em vez de
  // remontar a lista a partir dela, buscamos a lista de novo pela rota já testada.
  const carregar = useCallback(() => {
    return api<CicloNaLista[]>("/ciclos").then(setAcompanhamentos).catch((err) =>
      setError(err instanceof ApiError ? err.message : "Não foi possível carregar os acompanhamentos. Recarregue a página."));
  }, []);

  useEffect(() => {
    void carregar();
  }, [carregar]);

  async function encerrar() {
    const alvo = encerrando!;
    setEncerrando(null);
    setError(null);
    try {
      await api(`/ciclos/${alvo.id}/encerrar`, { method: "POST" });
      await carregar();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível encerrar o acompanhamento.");
    }
  }

  function abrirGerarLink(c: CicloNaLista) {
    setGerandoPara(c);
    setNEstudantes("");
    setDias("7");
    setColetadoEm(localDateInput());
    setGerarErro(null);
  }

  const prontoGerar = (() => {
    const n = Number(nEstudantes);
    const d = Number(dias);
    return Number.isInteger(n) && n > 0 && n <= 200 && Number.isInteger(d) && d > 0 && d <= 90 && coletadoEm !== "";
  })();

  async function gerarLink() {
    const alvo = gerandoPara!;
    setGerarErro(null);
    setGerando(true);
    try {
      const resultado = await api<LinkQtiGerado>(`/ciclos/${alvo.id}/qti/link`, {
        method: "POST",
        json: { n_estudantes: Number(nEstudantes), dias: Number(dias), coletado_em: coletadoEm },
      });
      setLinkGerado({ ...resultado, cicloId: alvo.id });
      setGerandoPara(null);
      await carregar();
    } catch (err) {
      setGerarErro(err instanceof ApiError ? err.message : "Não foi possível gerar o link.");
    } finally {
      setGerando(false);
    }
  }

  async function copiarLink(url: string) {
    try {
      await navigator.clipboard.writeText(url);
    } catch {
      // Navegador sem suporte à área de transferência: a URL já está visível na tela
      // para o professor copiar à mão.
    }
  }

  async function revogar() {
    const alvo = revogando!;
    setRevogando(null);
    setError(null);
    try {
      await api(`/qti/links/${alvo.linkId}/revogar`, { method: "POST" });
      setLinkGerado((atual) => (atual?.id === alvo.linkId ? null : atual));
      await carregar();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível revogar o link.");
    }
  }

  const comecar = <Link className="btn btn--primary" to="/ciclos/novo">Começar um acompanhamento</Link>;

  return (
    <>
      <div className="page__header">
        <h1>Meus acompanhamentos</h1>
        {acompanhamentos && acompanhamentos.length > 0 && comecar}
      </div>
      {error && <Banner kind="error">{error}</Banner>}
      {acompanhamentos === null && !error && <p role="status">Carregando…</p>}
      {acompanhamentos?.length === 0 && (
        <EmptyState title="Nenhum acompanhamento ainda" action={comecar}>
          Um acompanhamento reúne as aulas de uma turma ao longo do tempo, para você enviar o questionário
          respondido pelos estudantes e ver a trajetória.
        </EmptyState>
      )}
      {acompanhamentos && acompanhamentos.length > 0 && (
        <ul className="list">
          {acompanhamentos.map((c) => (
            <li key={c.id} className="list__item">
              <div>
                <p>{c.turma.name} · {c.disciplina.name}</p>
                <p className="meta">
                  Início em {formatDate(c.iniciado_em)} ·{" "}
                  {c.encerrado_em ? `Encerrado em ${formatDate(c.encerrado_em)}` : "Em andamento"} ·{" "}
                  {c.n_aulas_previstas} aulas previstas
                </p>
                <p className="meta">
                  <Link to={`/ciclos/${c.id}/relatorio`}>Ver o acompanhamento</Link>
                  {" · "}
                  <Link to={`/ciclos/${c.id}/qti`}>Enviar o relatório do questionário</Link>
                  {" · "}
                  <Button variant="tertiary" onClick={() => abrirGerarLink(c)}>Gerar link</Button>
                  {!c.encerrado_em && (
                    <>
                      {" · "}
                      <Button variant="tertiary" onClick={() => setEncerrando(c)}>Encerrar acompanhamento</Button>
                    </>
                  )}
                </p>
                {c.links_qti.length > 0 && (
                  <ul className="meta">
                    {c.links_qti.map((l) => (
                      <li key={l.id}>
                        Link para os estudantes válido até {formatDate(l.expira_em)}, até {l.limite_respostas} respostas
                        {" — "}
                        <Button variant="tertiary" onClick={() => setRevogando({ cicloId: c.id, linkId: l.id })}>
                          Revogar link
                        </Button>
                      </li>
                    ))}
                  </ul>
                )}
                {linkGerado && linkGerado.cicloId === c.id && (
                  <Banner kind="success">
                    <p>{linkGerado.url}</p>
                    <Button variant="tertiary" onClick={() => void copiarLink(linkGerado.url)}>Copiar link</Button>
                    <p>Guarde-o agora: não será possível vê-lo de novo.</p>
                  </Banner>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
      {encerrando && (
        <Dialog title={`Encerrar o acompanhamento de ${encerrando.turma.name}?`} onClose={() => setEncerrando(null)}
          actions={<>
            <Button variant="tertiary" onClick={() => setEncerrando(null)}>Cancelar</Button>
            <Button onClick={() => void encerrar()}>Confirmar encerramento</Button>
          </>}>
          <p>
            A última aula passa a precisar do questionário respondido pelos estudantes para gerar o relatório —
            é ela que fecha a comparação com o começo.
          </p>
          <p>Isto não pode ser desfeito por aqui.</p>
        </Dialog>
      )}
      {gerandoPara && (
        <Dialog title={`Gerar link para os estudantes de ${gerandoPara.turma.name}`} onClose={() => setGerandoPara(null)}
          actions={<>
            <Button variant="tertiary" onClick={() => setGerandoPara(null)}>Cancelar</Button>
            <Button onClick={() => void gerarLink()} disabled={!prontoGerar || gerando}>Gerar</Button>
          </>}>
          <p>Gerar um novo link para a mesma data desativa o anterior: o QR code que estiver projetado deixa de funcionar.</p>
          <div className="form-grid">
            <TextField label="Quantos estudantes tem a turma?" type="number" min={1} max={200} required
              value={nEstudantes} onChange={(e) => setNEstudantes(e.target.value)} />
            <TextField label="Quando a turma vai responder" type="date" required
              value={coletadoEm} onChange={(e) => setColetadoEm(e.target.value)} />
            <TextField label="Por quantos dias o link vale" type="number" min={1} max={90} required
              value={dias} onChange={(e) => setDias(e.target.value)} />
          </div>
          {gerarErro && <Banner kind="error">{gerarErro}</Banner>}
        </Dialog>
      )}
      {revogando && (
        <Dialog title="Revogar este link?" onClose={() => setRevogando(null)}
          actions={<>
            <Button variant="tertiary" onClick={() => setRevogando(null)}>Cancelar</Button>
            <Button onClick={() => void revogar()}>Confirmar revogação</Button>
          </>}>
          <p>Quem já tiver este link deixa de conseguir responder por ele.</p>
        </Dialog>
      )}
    </>
  );
}
