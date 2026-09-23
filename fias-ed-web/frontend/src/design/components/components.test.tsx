import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { expect, test, vi } from "vitest";
import type { FaixaIntervalo } from "../../api/types";
import { Banner } from "./Banner";
import { Button } from "./Button";
import { Dialog } from "./Dialog";
import { FaixaDeTempo, LARGURA_MINIMA_BLOCO_PX } from "./FaixaDeTempo";
import { TextField } from "./Field";
import { StatusBadge } from "./StatusBadge";

test("TextField associa rótulo e erro", () => {
  render(<TextField label="Usuário" error="Obrigatório" />);
  const input = screen.getByLabelText("Usuário");
  expect(input).toHaveAttribute("aria-invalid", "true");
  expect(input).toHaveAccessibleDescription("Obrigatório");
});

test("Button é type=button por padrão", () => {
  render(<Button>Salvar</Button>);
  expect(screen.getByRole("button", { name: "Salvar" })).toHaveAttribute("type", "button");
});

test("Dialog fecha com Esc e tem nome acessível", async () => {
  const onClose = vi.fn();
  render(<Dialog title="Excluir aula?" onClose={onClose} actions={<Button>Ok</Button>}>Texto</Dialog>);
  expect(screen.getByRole("dialog", { name: "Excluir aula?" })).toBeInTheDocument();
  await userEvent.keyboard("{Escape}");
  expect(onClose).toHaveBeenCalled();
});

// Revisão da Task 15: um `onClose` inline (nova identidade a cada render, comum em formulários
// controlados) não pode roubar o foco de um campo enquanto o usuário digita, e o Esc deve chamar
// a versão mais recente de `onClose` (fechando sobre o estado atual), não a de quando montou.
test("Dialog mantém o foco ao digitar e chama a versão mais recente do onClose no Esc", async () => {
  const chamadas: string[] = [];
  function Wrapper() {
    const [valor, setValor] = useState("");
    return (
      <Dialog title="Editar" onClose={() => chamadas.push(valor)} actions={<Button>Ok</Button>}>
        <TextField label="Campo" value={valor} onChange={(e) => setValor(e.target.value)} />
      </Dialog>
    );
  }
  render(<Wrapper />);
  const input = screen.getByLabelText("Campo");
  await userEvent.type(input, "abcde");
  expect(input).toHaveValue("abcde");
  expect(input).toHaveFocus();
  await userEvent.keyboard("{Escape}");
  expect(chamadas).toEqual(["abcde"]);
});

test("Banner de erro é alerta", () => {
  render(<Banner kind="error">Falhou</Banner>);
  expect(screen.getByRole("alert")).toHaveTextContent("Falhou");
});

test("StatusBadge mostra texto humano", () => {
  render(<StatusBadge status="AUDIO_VALIDATED" />);
  expect(screen.getByText("Áudio conferido")).toBeInTheDocument();
});

test("texto hostil é renderizado como texto", () => {
  render(<Banner>{"<script>alert(1)</script>"}</Banner>);
  expect(screen.getByRole("status").textContent).toBe("<script>alert(1)</script>");
  expect(document.querySelector("script")).toBeNull();
});

// ---- FaixaDeTempo: o que a tela AFIRMA quando o bloco não cabe nela.
//
// jsdom não faz layout e não tem ResizeObserver, então aqui os dois são
// simulados: o que se exerce é a decisão que depende da largura real, não a
// geometria. A geometria é medida em Chrome de verdade, fora daqui.

/** Uma aula de 45 min com o grupo mudando a cada intervalo de 3s: 900 blocos. */
const AULA_PICADA: FaixaIntervalo[] = Array.from({ length: 900 }, (_, i) => ({
  inicio_ms: i * 3000,
  fim_ms: (i + 1) * 3000,
  grupo: (["indireta", "direta", "estudante", "silêncio"] as const)[i % 4],
}));

function comLarguraDe(larguraPx: number) {
  class ObservadorDeTamanho {
    constructor(private aoMudar: ResizeObserverCallback) {}
    observe() {
      this.aoMudar([{ contentRect: { width: larguraPx } } as ResizeObserverEntry], this as unknown as ResizeObserver);
    }
    unobserve() {}
    disconnect() {}
  }
  vi.stubGlobal("ResizeObserver", ObservadorDeTamanho);
}

test("num celular a faixa diz que mostra o que mais apareceu em cada trecho, e diz quanto dura o trecho", () => {
  comLarguraDe(328); // 360px de celular menos o respiro de .page
  try {
    render(<FaixaDeTempo faixa={AULA_PICADA} />);
    // 900 blocos de 0,35px cada não cabem em 328px: a faixa para de afirmar o
    // grupo de cada instante e passa a afirmar o dominante de cada 35s — e diz
    // isso, em português, sem jargão.
    expect(screen.getByText(/mostra o que mais apareceu em cada 35 segundos de aula/i)).toBeInTheDocument();
    const grafico = screen.getByRole("img", { name: /distribuição da fala/i });
    const rects = [...grafico.querySelectorAll("rect")];
    expect(rects.length).toBeLessThan(100);
    const duracaoMs = Number(grafico.getAttribute("viewBox")!.split(" ")[2]);
    const emPixels = (r: Element) => (Number(r.getAttribute("width")) / duracaoMs) * 328;
    // 3px é o joelho medido em Chrome, não a constante do módulo: um teste que
    // se compara com a própria constante passa mesmo se ela cair para 1.
    expect(LARGURA_MINIMA_BLOCO_PX).toBeGreaterThanOrEqual(3);
    expect(Math.min(...rects.map(emPixels))).toBeGreaterThanOrEqual(3);
  } finally {
    vi.unstubAllGlobals();
  }
});

test("o resumo em palavras continua saindo da aula inteira, com as porcentagens exatas", () => {
  // A alternativa textual é quem carrega o dado exato: resumir a tela não pode
  // mexer nela. Os quatro grupos ocupam 25% cada nesta aula.
  comLarguraDe(328);
  try {
    render(<FaixaDeTempo faixa={AULA_PICADA} />);
    const rotulo = screen.getByRole("img", { name: /distribuição da fala/i }).getAttribute("aria-label")!;
    for (const nome of [/25% de influência indireta/i, /25% de influência direta/i, /25% de fala dos estudantes/i, /25% de silêncio/i]) {
      expect(rotulo).toMatch(nome);
    }
  } finally {
    vi.unstubAllGlobals();
  }
});

test("sem largura medida, a faixa mostra o dado intervalo a intervalo e não afirma trecho nenhum", () => {
  // Primeira pintura (e jsdom, que não tem ResizeObserver): só se resume o que
  // se mediu — e não se promete na tela um trecho que não se calculou.
  expect(typeof ResizeObserver).toBe("undefined");
  render(<FaixaDeTempo faixa={AULA_PICADA} />);
  expect(screen.getByRole("img", { name: /distribuição da fala/i }).querySelectorAll("rect")).toHaveLength(900);
  expect(screen.queryByText(/mostra o que mais apareceu/i)).not.toBeInTheDocument();
});
