import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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
