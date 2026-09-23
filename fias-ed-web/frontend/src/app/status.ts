const ANALISANDO = "Analisando sua aula…";
const INTERPRETANDO = "Preparando a interpretação pedagógica…";
const PADROES = "Padrões de interação prontos";

export const STATUS_TEXT: Record<string, string> = {
  DRAFT: "Aguardando o áudio da aula",
  AUDIO_IMPORTED: "Áudio recebido, pronto para processar",
  AUDIO_VALIDATED: "Áudio conferido",
  PREPROCESSING: ANALISANDO,
  TRANSCRIBING: ANALISANDO,
  TRANSCRIBED: ANALISANDO,
  DIARIZING: ANALISANDO,
  READY_FOR_SPEAKER_REVIEW: "Confirme qual voz é a sua",
  READY_FOR_TRANSCRIPT_REVIEW: "Revise a transcrição, se quiser",
  READY_FOR_FIAS: ANALISANDO,
  FIAS_COMPLETED: PADROES,
  WAITING_QTI: "Aguardando a percepção dos estudantes",
  QTI_COMPLETED: INTERPRETANDO,
  TRIANGULATED: INTERPRETANDO,
  MTSS_INTERPRETED: INTERPRETANDO,
  REPORT_READY: "Relatório da aula disponível",
  ERROR: "Precisa de atenção",
};

const PREPARANDO = "Preparando sua aula…";

/** Mensagens do prompt §36, por estágio: dizem o que está acontecendo com a aula do
 * professor, nunca o que o sistema está rodando (§86). */
const PROGRESSO: Record<string, string> = {
  PREPROCESSING: PREPARANDO,
  TRANSCRIBING: "Transformando áudio em texto…",
  // TRANSCRIBED é o repouso entre "a transcrição terminou" e "a separação de vozes
  // começou" (handle_transcribe grava o status e só então enfileira a diarização).
  // Repetir aqui a frase do DIARIZING afirmava um trabalho que ainda não tinha
  // começado — e deixava os dois estados idênticos na tela. Esta diz o que já
  // existe e o que vem depois, sem prometer que já está acontecendo.
  TRANSCRIBED: "Texto da aula pronto. O próximo passo é separar as vozes.",
  DIARIZING: "Identificando os momentos de fala…",
  READY_FOR_FIAS: "Analisando padrões da aula…",
};

/** Mensagem a mostrar enquanto a aula avança sozinha, ou `null` se ela estiver parada
 * esperando o professor — dizer "preparando" a uma aula parada seria mentira. */
export function progressMessage(status: string, jobAtivo: boolean): string | null {
  return PROGRESSO[status] ?? (jobAtivo ? PREPARANDO : null);
}

export type Tone = "progress" | "attention" | "done";

const ATTENTION = new Set(["ERROR", "DRAFT", "READY_FOR_SPEAKER_REVIEW", "READY_FOR_TRANSCRIPT_REVIEW", "WAITING_QTI"]);
// READY_FOR_FIAS fica de fora: ali a classificação ainda não rodou (a rota de
// padrões devolve 409), então "Padrões de interação prontos" com tom de concluído
// prometia ao professor uma tela que ele não consegue abrir. O estado é de
// progresso, e o badge diz o mesmo que o aviso logo abaixo dele.
const DONE = new Set(["AUDIO_IMPORTED", "AUDIO_VALIDATED", "FIAS_COMPLETED", "REPORT_READY"]);

export function statusText(status: string): string {
  return STATUS_TEXT[status] ?? "Em andamento";
}

export function statusTone(status: string): Tone {
  if (ATTENTION.has(status)) return "attention";
  if (DONE.has(status)) return "done";
  return "progress";
}
