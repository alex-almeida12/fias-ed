# Privacidade e proteção de dados

Este documento descreve o que o FIAS-ED coleta, para quê, onde fica, por
quanto tempo, quem acessa, como é excluído, como é anonimizado/pseudonimizado
e o que é exportado — com base apenas no projeto de ética em pesquisa (CEP),
nos termos de consentimento citados na dissertação e no comportamento real
do código (`export.py`, schemas de entidades). Nada aqui declara uma base
legal da LGPD: essa decisão cabe ao pesquisador, em conjunto com o Comitê de
Ética em Pesquisa.

**Base legal: a definir pelo pesquisador com o CEP (PENDING).**

## Dados coletados, por entidade

| Entidade | Dados coletados | Contém dado pessoal sensível? |
|---|---|---|
| Professor | Nome de exibição, papel de acesso, nome de usuário | Sim (identifica o professor) |
| Escola, Turma, Disciplina | Nome, município, região, ano letivo, nível | Não diretamente |
| Aula | Data, status do pipeline, anotações | Não diretamente |
| Audio | Arquivo de áudio original (voz do professor e de estudantes), metadados técnicos | Sim (voz é dado biométrico potencial — ver "Não fazemos") |
| Transcricao / Segmento | Texto transcrito (`texto_original_asr`, `texto_revisado`) | Sim (pode conter nomes e falas de estudantes) |
| Falante | Rótulo de diarização + papel (`PROFESSOR`/`ALUNO`) | Não persiste identidade individual do estudante |
| ClassificacaoFIAS / IndicadorFIAS | Categorias e índices FIAS calculados | Não (dado derivado, agregado da fala) |
| QuestionarioQTI / RespostaQTI / ResultadoQTI | Respostas ao QTI-24 (Likert 1–5), sem identificação do respondente | Não (estudante responde anonimamente — ver `QTI.md`) |
| Triangulacao / ResultadoMTSS / Recomendacao | Dados derivados (índices, regras disparadas, sugestões) | Não |
| Relatorio | PDF gerado, hash | Reflete os dados acima |
| Processamento | Metadados técnicos de execução | Não |
| ModeloIA | Metadados de modelos | Não |

## Finalidade

Diagnóstico e apoio à reflexão docente sobre a própria prática em sala de
aula, no âmbito da pesquisa "Framework FIAS-ED" (PPgCC UFERSA/UERN), gerando
relatórios individuais para o professor participante.

## Localização

- **Web**: PC do pesquisador; ambiente Docker; volume local (sem envio a
  serviços de terceiros por padrão).
- **Android**: armazenamento privado do aplicativo no dispositivo do
  professor.
- Armazenamento em três níveis, de acordo com CAP5 l.107: dados brutos no
  celular do professor, criptografados; dados processados no repositório
  institucional da UFERSA, com acesso restrito; dados agregados em ambiente
  de acesso controlado.

## Retenção

Prazo de retenção: 5 anos após a conclusão da pesquisa, com destruição
certificada (CAP5 l.109; CEP l.95). A retirada de consentimento é garantida
"nos cinco anos seguintes" à coleta.

## Acesso

- Pesquisador responsável e orientador têm acesso aos dados, autorização
  prevista no TCLE (Anexo A).
- Cada professor participante recebe o relatório individual da própria aula
  e não tem acesso às aulas de outros professores.

## Exclusão

Exclusão **real** (remoção física, não soft delete) para áudio e
transcrição, alinhado a CEP l.85 ("o áudio original permanece restrito ao
dispositivo do professor") e à retirada de consentimento garantida no TCLE.
As demais entidades usam soft delete (`deleted_at`), preservando o histórico
necessário à reprodutibilidade científica — ver `DATABASE_MODEL.md`.

## Anonimização e pseudonimização

- Códigos opacos identificam professores e turmas nos dados de pesquisa
  (CEP l.93–94; CAP5 l.84).
- O QTI não tem campos identificatórios do estudante que responde.
- Nomes próprios são removidos por NER (reconhecimento de entidades
  nomeadas) antes de qualquer exportação com texto — esta etapa é
  **opcional e ainda `PENDING_SCIENTIFIC_VALIDATION`** (não há validação da
  qualidade do NER nas fontes). O resultado é um texto com nomes
  substituídos por `[NOME]`, guardado em `Segmento.text_pseudonymized` (só
  presente quando a etapa de NER já rodou).
- Auto-identificação de um estudante na fala (dizer o próprio nome) é
  substituída por um token anônimo, no mesmo processo de NER.
- Na exportação da turma para o QTI, o sistema `avalie-seu-professor` usa
  `age_band` (faixa etária) em vez de idade exata, e nunca coleta nome do
  respondente.

## Exportação

`fias_ed_engine.export.build_dataset` (ver `DATABASE_MODEL.md`):

- Por padrão, o dataset exportado **não contém texto de falas**.
- A opção `include_text` inclui apenas `text_pseudonymized`; se qualquer
  segmento selecionado não tiver essa versão, a exportação inteira é
  recusada (`ExportPrivacyError`).
- Nunca são exportados: áudio, caminhos de arquivo, nome do professor, nome
  da turma, `texto_original_asr` ou dados de login.
- A turma aparece apenas pelo `turma_id` (UUID); a disciplina aparece pelo
  nome.
- O `manifest` da exportação registra versão, opções usadas, quantidade de
  aulas, modelos e hashes usados e a data — para permitir auditoria de quem
  exportou o quê, mas sem dado pessoal adicional.

## Não fazemos

- Biometria de voz (nenhuma técnica de biometria é usada para identificar
  quem fala).
- Reconhecimento facial.
- Identificação individual de estudante por voz.
- Envio de áudio ou transcrição a APIs externas sem autorização explícita
  do professor (CEP l.85: "áudio não vai a servidores sem autorização
  explícita"; codificadores só veem transcrições anonimizadas).

## Divergências a resolver

- **UFERSA × UERN**: o projeto CEP está vinculado à UERN; CAP5 l.82 menciona
  a UFERSA. As fontes não resolvem qual instituição é a responsável formal
  perante o Comitê de Ética — decisão do pesquisador.
- **Princípios AIED Unplugged**: CAP4 l.115 e CEP l.55 listam princípios com
  redações diferentes (ver `RESEARCH_INVENTORY.md` §6) — não afeta
  diretamente a privacidade de dados, mas é registrado aqui porque ambos os
  textos tratam do mesmo compromisso de robustez a restrições tecnológicas
  que também embasa o armazenamento local por padrão.
- **Modo cloud/LLM**: nenhuma fonte (TCLE, TALE, projeto CEP) cobre
  explicitamente o cenário em que o processamento usa uma API de LLM em
  nuvem (modo cloud citado no spec §"Modos offline/intermitente/cloud").
  Enquanto essa cobertura não existir nos termos de consentimento, o modo
  cloud não deve processar áudio ou transcrição de aulas reais sem uma
  decisão explícita do pesquisador junto ao CEP.

## Termos de consentimento

TCLE (professores e responsáveis por estudantes menores), TALE (estudantes),
e termo específico de áudio para entrevistas (CEP l.168). Este documento não
substitui nem resume os termos completos; ele apenas referencia onde cada
prática de dado está prevista neles.
