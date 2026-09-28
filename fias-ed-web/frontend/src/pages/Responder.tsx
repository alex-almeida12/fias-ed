import { useEffect, useState } from "react";
import { useParams } from "react-router";
import type { QtiQuestionario } from "../api/types";
import { Banner } from "../design/components/Banner";
import { Button } from "../design/components/Button";

// A única tela do sistema sem conta e sem sessão de professor (§10 da spec):
// o link público não passa pelo cliente `api()` de `../api/client` de
// propósito — aquele helper sempre prefixa `/api` e manda o cookie CSRF da
// sessão do professor, e as rotas públicas vivem fora de `/api`, sem sessão
// nenhuma (ver `app/publico/routes.py`, comentário "a ausência do prefixo é
// física, não cosmética").
async function chamarPublico<T>(caminho: string, corpo?: unknown): Promise<T> {
  const init: RequestInit = { credentials: "same-origin" };
  if (corpo !== undefined) {
    init.method = "POST";
    init.headers = { "Content-Type": "application/json" };
    init.body = JSON.stringify(corpo);
  }
  const res = await fetch(caminho, init);
  const dados: unknown = await res.json().catch(() => null);
  if (!res.ok) {
    const mensagem = dados && typeof dados === "object" && "message" in dados && typeof dados.message === "string"
      ? dados.message : "Algo deu errado. Tente novamente.";
    throw new Error(mensagem);
  }
  return dados as T;
}

// Achado desta tarefa: o brief não menciona corpo nenhum para `/consentir`,
// mas `ConsentirIn` no backend exige `documento_versao` (min_length=1) — sem
// ela o POST real cai em 422, embora o teste com mock não perceba a ausência
// (ele não inspeciona o corpo da requisição). "1.0.0" é o valor usado em
// todos os testes de backend porque o texto legal do termo de consentimento
// ainda é uma pendência do comitê de ética (spec §5, "Pendência do
// pesquisador"): qualquer versão não vazia serve até esse texto existir.
const DOCUMENTO_VERSAO = "1.0.0";

type Etapa = "carregando" | "erro" | "consentimento" | "formulario" | "agradecimento";

function chaveRespondido(token: string): string {
  return `fias-ed:respondido:${token}`;
}

export function Responder() {
  const { token = "" } = useParams();
  const [etapa, setEtapa] = useState<Etapa>(() =>
    localStorage.getItem(chaveRespondido(token)) === "1" ? "agradecimento" : "carregando");
  const [questionario, setQuestionario] = useState<QtiQuestionario | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [respostas, setRespostas] = useState<Record<number, number>>({});
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    if (etapa !== "carregando") return;
    chamarPublico<QtiQuestionario>(`/publico/qti/${token}`)
      .then((q) => { setQuestionario(q); setEtapa("consentimento"); })
      .catch((err: unknown) => {
        setErro(err instanceof Error ? err.message : "Não foi possível abrir o questionário.");
        setEtapa("erro");
      });
  }, [etapa, token]);

  async function concordar() {
    setErro(null);
    try {
      await chamarPublico(`/publico/qti/${token}/consentir`, { documento_versao: DOCUMENTO_VERSAO });
      setEtapa("formulario");
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Não foi possível registrar seu consentimento.");
    }
  }

  function escolher(order: number, valor: number) {
    setRespostas((atual) => ({ ...atual, [order]: valor }));
  }

  const pronto = questionario !== null && questionario.itens.every((item) => item.order in respostas);

  async function enviar() {
    if (!pronto) return;
    setErro(null);
    setEnviando(true);
    try {
      const corpo: Record<string, number> = {};
      for (const [ordem, valor] of Object.entries(respostas)) corpo[ordem] = valor;
      await chamarPublico(`/publico/qti/${token}/responder`, { respostas: corpo });
      localStorage.setItem(chaveRespondido(token), "1");
      setEtapa("agradecimento");
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Não foi possível enviar suas respostas.");
    } finally {
      setEnviando(false);
    }
  }

  if (etapa === "carregando") return null;

  if (etapa === "erro") {
    return (
      <main className="page">
        <Banner kind="error">{erro}</Banner>
      </main>
    );
  }

  if (etapa === "agradecimento") {
    return (
      <main className="page">
        <h1>Obrigado(a) por participar</h1>
        <p>Você já respondeu a este questionário neste navegador.</p>
      </main>
    );
  }

  if (etapa === "consentimento" && questionario) {
    return (
      <main className="page">
        <h1>Antes de começar</h1>
        <p>
          Este questionário tem {questionario.itens.length} perguntas sobre a interação em
          sala de aula. Ninguém saberá quem respondeu: suas respostas não são ligadas ao seu
          nome nem a este aparelho.
        </p>
        {erro && <Banner kind="error">{erro}</Banner>}
        <Button onClick={concordar}>Eu concordo em responder</Button>
      </main>
    );
  }

  if (!questionario) return null;

  return (
    <main className="page">
      <h1>Questionário</h1>
      <p>{questionario.stem}</p>
      {questionario.itens.map((item) => (
        <fieldset className="likert" key={item.order}>
          <legend className="likert__legenda">{item.order}. {item.text}</legend>
          <div className="likert__escala">
            <span className="likert__rotulo">{questionario.escala.min_label}</span>
            <div className="likert__opcoes">
              {Array.from(
                { length: questionario.escala.max - questionario.escala.min + 1 },
                (_, i) => questionario.escala.min + i,
              ).map((valor) => (
                <label className="likert__opcao" key={valor}>
                  <input type="radio" name={`pergunta-${item.order}`} value={valor}
                    checked={respostas[item.order] === valor}
                    onChange={() => escolher(item.order, valor)} />
                  <span>{valor}</span>
                </label>
              ))}
            </div>
            <span className="likert__rotulo">{questionario.escala.max_label}</span>
          </div>
        </fieldset>
      ))}
      {erro && <Banner kind="error">{erro}</Banner>}
      <Button onClick={enviar} disabled={!pronto || enviando}>Enviar respostas</Button>
    </main>
  );
}
