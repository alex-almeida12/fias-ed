import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { expect, test, vi } from "vitest";
import { Banner } from "./Banner";
import { Button } from "./Button";
import { Dialog } from "./Dialog";
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
