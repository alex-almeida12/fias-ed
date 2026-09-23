import "@testing-library/jest-dom/vitest";
import { cleanup, configure } from "@testing-library/react";
import { afterEach, vi } from "vitest";

// Prazo do `findBy*`/`waitFor` (padrão do testing-library: 1000 ms). É ele — não o
// `testTimeout` do vitest — que produz "Unable to find role=...".
//
// Medido nesta máquina (16 CPUs, 15 arquivos em paralelo), instrumentando os dois
// testes que falhavam. O que eles esperam não é um render raso: é montar o App inteiro
// (router + AuthProvider) e encadear DUAS idas à API em série — /auth/me e só então
// /turmas (ou /aulas/:id/vozes). Com a máquina ociosa isso já custa 219–311 ms. O
// padrão de 1000 ms dava a esta suíte uma folga de 3–4x, não os 25x que o número
// sugere; qualquer concorrência de CPU come essa folga.
//
//   máquina ociosa           suíte em   6,5–8,2 s   elemento em 219–311 ms   passou
//   + 24 threads girando     suíte em  36–46 s      elemento > 1000 ms       0/5 passaram
//   + 32 threads girando     suíte em  60–116 s     elemento > 1000 ms       0/6 passaram
//   + 64 threads girando     suíte em  96–119 s     elemento > 1000 ms       0/3 passaram
//
// É inanição de escalonamento, não corrida: sob as MESMAS cargas, só que com prazo de
// 30–60 s, a suíte passou 8/8 e o elemento SEMPRE apareceu — em 223–850 ms no comum e
// 5844 ms no pior caso observado. Uma corrida de verdade continuaria falhando por mais
// que se esperasse. Esperar mais aqui não esconde defeito: um elemento que não existe
// continua não aparecendo, e o teste ainda falha dizendo QUAL elemento faltou, porque
// 10 s < os 30 s de `testTimeout` (verificado removendo de propósito as <option> de
// turma e o handler do botão de escolher voz).
//
// 10 s = 1,7x o pior caso medido sob carga (5844 ms) e 32x o pior caso ocioso.
configure({ asyncUtilTimeout: 10_000 });

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  // ponytail: alguns testes (ex.: lint.test.ts) rodam com @vitest-environment node,
  // onde `document` não existe; guarda evita ReferenceError nesses arquivos.
  if (typeof document !== "undefined") {
    document.cookie = "fias_csrf=; expires=Thu, 01 Jan 1970 00:00:00 GMT";
  }
});
