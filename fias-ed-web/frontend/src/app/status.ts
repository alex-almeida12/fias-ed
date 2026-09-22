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
  READY_FOR_FIAS: PADROES,
  FIAS_COMPLETED: PADROES,
  WAITING_QTI: "Aguardando a percepção dos estudantes",
  QTI_COMPLETED: INTERPRETANDO,
  TRIANGULATED: INTERPRETANDO,
  MTSS_INTERPRETED: INTERPRETANDO,
  REPORT_READY: "Relatório da aula disponível",
  ERROR: "Precisa de atenção",
};

/** Mensagem do prompt §36 para a etapa executada em W1 (validação do áudio). */
export const JOB_MESSAGE = "Preparando sua aula...";

export type Tone = "progress" | "attention" | "done";

const ATTENTION = new Set(["ERROR", "DRAFT", "READY_FOR_SPEAKER_REVIEW", "READY_FOR_TRANSCRIPT_REVIEW", "WAITING_QTI"]);
const DONE = new Set(["AUDIO_IMPORTED", "AUDIO_VALIDATED", "READY_FOR_FIAS", "FIAS_COMPLETED", "REPORT_READY"]);

export function statusText(status: string): string {
  return STATUS_TEXT[status] ?? "Em andamento";
}

export function statusTone(status: string): Tone {
  if (ATTENTION.has(status)) return "attention";
  if (DONE.has(status)) return "done";
  return "progress";
}
