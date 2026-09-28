import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import { ADMIN, jsonResponse, mockApi, PROFESSORA, renderApp } from "../../test-utils";

const CONTA = { id: "p1", username: "ana", display_name: "Ana Souza", role: "PROFESSOR", is_active: true,
  must_change_password: false, created_at: "2026-09-22T10:00:00+00:00" };

test("professor não acessa telas de administração", async () => {
  mockApi({ "GET /api/auth/me": () => jsonResponse(PROFESSORA), "GET /api/aulas": () => jsonResponse([]) });
  renderApp("/admin/contas");
  await waitFor(() => expect(window.location.pathname).toBe("/aulas"));
});

test("criar conta mostra a senha provisória uma vez", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(ADMIN),
    "GET /api/admin/contas": () => jsonResponse([CONTA]),
    "POST /api/admin/contas": () => jsonResponse({ conta: { ...CONTA, id: "p2", username: "bia", display_name: "Bia" },
      senha_provisoria: "Prov-Senha-123" }, 201),
  });
  renderApp("/admin/contas");
  await userEvent.type(await screen.findByLabelText("Nome de usuário"), "bia");
  await userEvent.type(screen.getByLabelText("Nome de exibição"), "Bia");
  await userEvent.click(screen.getByRole("button", { name: "Criar conta" }));
  expect(await screen.findByText(/Prov-Senha-123/)).toBeInTheDocument();
  expect(screen.getByText(/não será mostrada de novo/)).toBeInTheDocument();
});

test("excluir conta exige digitar o nome de usuário", async () => {
  let deleted = false;
  mockApi({
    "GET /api/auth/me": () => jsonResponse(ADMIN),
    "GET /api/admin/contas": () => jsonResponse(deleted ? [] : [CONTA]),
    "DELETE /api/admin/contas/p1": (init) => {
      expect(JSON.parse(String(init!.body))).toEqual({ confirmar_username: "ana" });
      deleted = true;
      return jsonResponse(null, 204);
    },
  });
  renderApp("/admin/contas");
  const row = (await screen.findByText("Ana Souza")).closest("tr")!;
  await userEvent.click(within(row).getByRole("button", { name: "Excluir" }));
  const dialog = screen.getByRole("dialog", { name: "Excluir a conta de Ana Souza?" });
  const confirmar = within(dialog).getByRole("button", { name: "Excluir conta" });
  expect(confirmar).toBeDisabled();
  await userEvent.type(within(dialog).getByLabelText("Digite ana para confirmar"), "ana");
  await userEvent.click(confirmar);
  await waitFor(() => expect(screen.queryByText("Ana Souza")).not.toBeInTheDocument());
});

test("agir como professor a partir da lista de aulas", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(ADMIN),
    "GET /api/admin/contas": () => jsonResponse([CONTA]),
    "GET /api/admin/aulas": () => jsonResponse([{ id: "a1", lesson_date: "2026-09-22", status: "AUDIO_VALIDATED",
      turma: { id: "t1", name: "9º B" }, disciplina: { id: "d1", name: "Ciências" },
      professor: { id: "p1", display_name: "Ana Souza" } }]),
    "POST /api/admin/agir-como": () => jsonResponse({ ...ADMIN, acting_as: { id: "p1", display_name: "Ana Souza" } }),
    "GET /api/aulas/a1": () => jsonResponse({ id: "a1", lesson_date: "2026-09-22", status: "AUDIO_VALIDATED",
      turma: { id: "t1", name: "9º B" }, disciplina: { id: "d1", name: "Ciências" }, note: null, error_code: null,
      error_message: null, audio: null, upload_pendente: null, job_ativo: false, alterada_pelo_admin_em: null,
      acompanhamento: null }),
  });
  renderApp("/admin/aulas");
  await userEvent.click(await screen.findByRole("button", { name: "Agir como Ana Souza" }));
  await waitFor(() => expect(window.location.pathname).toBe("/aulas/a1"));
  expect(await screen.findByText("Você está agindo como: Ana Souza")).toBeInTheDocument();
});

test("agir como professor sem aulas, a partir de Contas", async () => {
  let body: unknown = null;
  mockApi({
    "GET /api/auth/me": () => jsonResponse(ADMIN),
    "GET /api/admin/contas": () => jsonResponse([CONTA, { ...CONTA, id: "a1", username: "admin", display_name: "Pesquisador",
      role: "ADMIN_LOCAL" }]),
    "POST /api/admin/agir-como": (init) => {
      body = JSON.parse(String(init!.body));
      return jsonResponse({ ...ADMIN, acting_as: { id: "p1", display_name: "Ana Souza" } });
    },
    "GET /api/aulas": () => jsonResponse([]),
  });
  renderApp("/admin/contas");
  const adminRow = (await screen.findByText("Pesquisador", { selector: "td" })).closest("tr")!;
  expect(within(adminRow).queryByRole("button", { name: /Agir como/ })).not.toBeInTheDocument();
  const row = screen.getByText("Ana Souza", { selector: "td" }).closest("tr")!;
  await userEvent.click(within(row).getByRole("button", { name: "Agir como Ana Souza" }));
  await waitFor(() => expect(window.location.pathname).toBe("/aulas"));
  expect(body).toEqual({ professor_id: "p1" });
  expect(await screen.findByText("Você está agindo como: Ana Souza")).toBeInTheDocument();
});

test("erro ao agir como professor a partir de Contas mostra aviso", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(ADMIN),
    "GET /api/admin/contas": () => jsonResponse([CONTA]),
    "POST /api/admin/agir-como": () => jsonResponse({ error_code: "CONTA_NAO_ENCONTRADA", message: "Conta não encontrada." }, 404),
  });
  renderApp("/admin/contas");
  await userEvent.click(await screen.findByRole("button", { name: "Agir como Ana Souza" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Conta não encontrada.");
  expect(window.location.pathname).toBe("/admin/contas");
});

test("juntar escolas duplicadas", async () => {
  let merged = false;
  const escolas = [
    { id: "e1", name: "Escola São José", municipality: "Mossoró", region: null },
    { id: "e2", name: "E. São José", municipality: "Mossoró", region: null },
  ];
  mockApi({
    "GET /api/auth/me": () => jsonResponse(ADMIN),
    "GET /api/escolas": () => jsonResponse(merged ? [escolas[0]] : escolas),
    "POST /api/admin/escolas/e2/juntar": (init) => {
      expect(JSON.parse(String(init!.body))).toEqual({ destino_id: "e1" });
      merged = true;
      return jsonResponse(escolas[0]);
    },
  });
  renderApp("/admin/escolas");
  const row = (await screen.findByDisplayValue("E. São José")).closest("tr")!;
  await userEvent.selectOptions(within(row).getByLabelText("Juntar com"), "e1");
  await userEvent.click(within(row).getByRole("button", { name: "Juntar" }));
  await waitFor(() => expect(screen.queryByDisplayValue("E. São José")).not.toBeInTheDocument());
});

// Ruling P8: a tela admin de Escolas deve permitir editar a região, incluindo limpá-la.
test("editar a região de uma escola", async () => {
  const escolas = [{ id: "e1", name: "Escola São José", municipality: "Mossoró", region: null }];
  mockApi({
    "GET /api/auth/me": () => jsonResponse(ADMIN),
    "GET /api/escolas": () => jsonResponse(escolas),
    "PATCH /api/admin/escolas/e1": (init) => {
      expect(JSON.parse(String(init!.body))).toEqual({ name: "Escola São José", municipality: "Mossoró", region: "Nordeste" });
      return jsonResponse({ ...escolas[0], region: "Nordeste" });
    },
  });
  renderApp("/admin/escolas");
  const row = (await screen.findByDisplayValue("Escola São José")).closest("tr")!;
  await userEvent.selectOptions(within(row).getByLabelText("Região"), "Nordeste");
  await userEvent.click(within(row).getByRole("button", { name: "Salvar" }));
  await waitFor(() => expect(within(row).getByLabelText("Região")).toHaveValue("Nordeste"));
});

// Ruling P15: carregar e agir sobre contas/aulas/escolas não devem falhar silenciosamente.
test("erro ao carregar contas mostra aviso", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(ADMIN),
    "GET /api/admin/contas": () => jsonResponse({ error_code: "ERRO", message: "Falha ao listar contas." }, 500),
  });
  renderApp("/admin/contas");
  expect(await screen.findByRole("alert")).toHaveTextContent("Falha ao listar contas.");
});

test("erro ao criar conta mostra aviso e não fecha o formulário", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(ADMIN),
    "GET /api/admin/contas": () => jsonResponse([]),
    "POST /api/admin/contas": () => jsonResponse({ error_code: "USUARIO_EXISTE", message: "Já existe uma conta com este nome de usuário." }, 409),
  });
  renderApp("/admin/contas");
  await userEvent.type(await screen.findByLabelText("Nome de usuário"), "ana");
  await userEvent.type(screen.getByLabelText("Nome de exibição"), "Ana");
  await userEvent.click(screen.getByRole("button", { name: "Criar conta" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Já existe uma conta com este nome de usuário.");
  expect(screen.getByLabelText("Nome de usuário")).toHaveValue("ana");
});

test("erro ao agir como professor mostra aviso", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(ADMIN),
    "GET /api/admin/contas": () => jsonResponse([CONTA]),
    "GET /api/admin/aulas": () => jsonResponse([{ id: "a1", lesson_date: "2026-09-22", status: "AUDIO_VALIDATED",
      turma: { id: "t1", name: "9º B" }, disciplina: { id: "d1", name: "Ciências" },
      professor: { id: "p1", display_name: "Ana Souza" } }]),
    "POST /api/admin/agir-como": () => jsonResponse({ error_code: "ERRO", message: "Não foi possível agir como este professor." }, 500),
  });
  renderApp("/admin/aulas");
  await userEvent.click(await screen.findByRole("button", { name: "Agir como Ana Souza" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Não foi possível agir como este professor.");
  expect(window.location.pathname).toBe("/admin/aulas");
});

test("erro ao carregar escolas mostra aviso", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(ADMIN),
    "GET /api/escolas": () => jsonResponse({ error_code: "ERRO", message: "Falha ao listar escolas." }, 500),
  });
  renderApp("/admin/escolas");
  expect(await screen.findByRole("alert")).toHaveTextContent("Falha ao listar escolas.");
});

test("erro ao juntar escolas mostra aviso", async () => {
  const escolas = [
    { id: "e1", name: "Escola São José", municipality: "Mossoró", region: null },
    { id: "e2", name: "E. São José", municipality: "Mossoró", region: null },
  ];
  mockApi({
    "GET /api/auth/me": () => jsonResponse(ADMIN),
    "GET /api/escolas": () => jsonResponse(escolas),
    "POST /api/admin/escolas/e2/juntar": () => jsonResponse({ error_code: "ERRO", message: "Não foi possível juntar as escolas." }, 500),
  });
  renderApp("/admin/escolas");
  const row = (await screen.findByDisplayValue("E. São José")).closest("tr")!;
  await userEvent.selectOptions(within(row).getByLabelText("Juntar com"), "e1");
  await userEvent.click(within(row).getByRole("button", { name: "Juntar" }));
  expect(await within(row).findByRole("alert")).toHaveTextContent("Não foi possível juntar as escolas.");
  expect(screen.getByDisplayValue("E. São José")).toBeInTheDocument();
});

// Ruling P15 (revisão): carregar deve limpar o erro anterior a cada tentativa — uma falha ao
// recarregar não pode deixar o aviso preso mesmo depois de um recarregamento seguinte ter êxito.
test("escolas: falha ao recarregar mostra aviso, e um recarregamento seguinte bem-sucedido o apaga", async () => {
  const escola = { id: "e1", name: "Escola São José", municipality: "Mossoró", region: null };
  let chamadasEscolas = 0;
  mockApi({
    "GET /api/auth/me": () => jsonResponse(ADMIN),
    "GET /api/escolas": () => {
      chamadasEscolas += 1;
      // 1ª chamada (montagem): sucesso. 2ª (recarregar após 1º Salvar): falha. 3ª (recarregar
      // após 2º Salvar): sucesso de novo.
      if (chamadasEscolas === 2) return jsonResponse({ error_code: "ERRO", message: "Falha ao listar escolas." }, 500);
      return jsonResponse([escola]);
    },
    "PATCH /api/admin/escolas/e1": () => jsonResponse(escola),
  });
  renderApp("/admin/escolas");
  const row = (await screen.findByDisplayValue("Escola São José")).closest("tr")!;
  await userEvent.click(within(row).getByRole("button", { name: "Salvar" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Falha ao listar escolas.");
  await userEvent.click(within(row).getByRole("button", { name: "Salvar" }));
  await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument());
});
