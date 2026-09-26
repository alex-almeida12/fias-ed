import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (BigInteger, Boolean, Date, DateTime, Enum, Float, ForeignKey, Index, Integer,
                        JSON, MetaData, String, literal_column)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.config import get_settings

AULA_STATUS = (
    "DRAFT", "AUDIO_IMPORTED", "AUDIO_VALIDATED", "PREPROCESSING", "TRANSCRIBING", "TRANSCRIBED",
    "DIARIZING", "READY_FOR_SPEAKER_REVIEW", "READY_FOR_TRANSCRIPT_REVIEW", "READY_FOR_FIAS",
    "FIAS_COMPLETED", "WAITING_QTI", "QTI_COMPLETED", "TRIANGULATED", "MTSS_INTERPRETED",
    "REPORT_READY", "ERROR",
)
SYNC_STATUS = ("LOCAL_ONLY", "PENDING_SYNC", "SYNCED", "CONFLICT")
ROLES = ("ADMIN_LOCAL", "PROFESSOR")
REGIONS = ("Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul")
MIME_TYPES = ("audio/mpeg", "audio/wav", "audio/x-wav", "audio/mp4", "audio/aac", "audio/flac", "audio/x-flac")
TRANSCRIPT_SOURCES = ("ASR_ORIGINAL", "TRANSCRICAO_REVISADA")
JOB_STATUS = ("queued", "running", "done", "failed")
ADMIN_ACTIONS = ("read", "create", "update", "delete", "upload", "process")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _device_id() -> str:
    return get_settings().device_id


def _enum(values: tuple, name: str) -> Enum:
    return Enum(*values, name=name, native_enum=False, create_constraint=True, length=32)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    })


class EntityMixin:
    """Campos comuns do _base.schema.json do shared."""
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow,
                                                 nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, onupdate=literal_column("version + 1"),
                                         nullable=False)
    sync_status: Mapped[str] = mapped_column(_enum(SYNC_STATUS, "sync_status"), default="LOCAL_ONLY",
                                             nullable=False)
    device_id: Mapped[str] = mapped_column(String(64), default=_device_id, nullable=False)


class Professor(EntityMixin, Base):
    __tablename__ = "professor"
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[str] = mapped_column(_enum(ROLES, "role"), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Escola(EntityMixin, Base):
    __tablename__ = "escola"
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    name_key: Mapped[str] = mapped_column(String(200), index=True, nullable=False)
    municipality: Mapped[str | None] = mapped_column(String(120), nullable=True)
    region: Mapped[str | None] = mapped_column(_enum(REGIONS, "region"), nullable=True)


class Turma(EntityMixin, Base):
    __tablename__ = "turma"
    escola_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escola.id"), nullable=False)
    professor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("professor.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    school_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    level: Mapped[str | None] = mapped_column(String(60), nullable=True)


class Disciplina(EntityMixin, Base):
    __tablename__ = "disciplina"
    professor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("professor.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)


class Aula(EntityMixin, Base):
    __tablename__ = "aula"
    professor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("professor.id"), index=True, nullable=False)
    turma_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("turma.id"), nullable=False)
    disciplina_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("disciplina.id"), nullable=False)
    lesson_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(_enum(AULA_STATUS, "aula_status"), default="DRAFT", nullable=False)
    note: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Audio(EntityMixin, Base):
    __tablename__ = "audio"
    aula_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("aula.id"), index=True, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    internal_filename: Mapped[str] = mapped_column(String(64), nullable=False)
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    mime_type: Mapped[str] = mapped_column(_enum(MIME_TYPES, "mime_type"), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    channels: Mapped[int] = mapped_column(Integer, nullable=False)
    sample_rate: Mapped[int] = mapped_column(Integer, nullable=False)
    is_original: Mapped[bool] = mapped_column(Boolean, nullable=False)
    derived_from_audio_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("audio.id"), nullable=True)


FALANTE_ROLES = ("PROFESSOR", "ALUNO", "UNASSIGNED")
LANGUAGES = ("pt-BR",)
MODEL_FORMATS = ("safetensors", "onnx", "ggml", "other")
INDICADOR_REASONS = ("insufficient_data",)
VALIDATION_STATUS = ("validated", "PENDING_SCIENTIFIC_VALIDATION", "engineering_decision",
                     "draft_pending_researcher_review")


class Transcricao(EntityMixin, Base):
    __tablename__ = "transcricao"
    aula_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("aula.id"), index=True, nullable=False)
    audio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("audio.id"), nullable=False)
    language: Mapped[str] = mapped_column(_enum(LANGUAGES, "transcricao_language"),
                                          default="pt-BR", nullable=False)
    asr_model_id: Mapped[str] = mapped_column(String, nullable=False)


class Falante(EntityMixin, Base):
    """Uma linha por voz enquanto role=UNASSIGNED; exatamente duas depois da
    escolha do professor (PROFESSOR e ALUNO). Nenhum agrupamento de voz por
    estudante sobrevive à escolha (§48)."""
    __tablename__ = "falante"
    transcricao_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("transcricao.id"), index=True,
                                                      nullable=False)
    diarization_label: Mapped[str] = mapped_column(String(32), nullable=False)
    role: Mapped[str] = mapped_column(_enum(FALANTE_ROLES, "falante_role"),
                                      default="UNASSIGNED", nullable=False)


class TrechoDeFala(Base):
    """A linha do tempo de fala da aula: de quando a quando houve voz, e
    QUANTAS ao mesmo tempo — nunca quais.

    Evidência de fala/não-fala, e é o único lugar onde ela existe depois que a
    cópia de trabalho do áudio é apagada no fim da diarização. Sem esta tabela a
    classificação FIAS — que só roda depois da revisão de vozes, horas ou dias
    depois — não teria como saber onde não houve fala, e mediria silêncio pelas
    lacunas entre segmentos do ASR, que é a medida errada: o vad_filter do
    Whisper cola as pausas para dentro dos segmentos.

    `n_vozes`, e não o rótulo do diarizador. O §48 proíbe agrupamento de voz por
    estudante em qualquer lugar, inclusive no banco: com (início, fim, rótulo)
    gravados, "o estudante da voz 01 falou nestes 45 momentos da aula" sai de um
    SELECT. Que o rótulo não signifique nada entre execuções não ajuda — dentro
    de uma aula ele significa, e é dentro de uma aula que a reidentificação
    acontece. A contagem basta para as duas regras que precisam desta evidência:
    silêncio quer saber se houve fala, e confusão (fias_rules.confusion, ainda
    não implementada) quer saber se havia mais de uma voz ao mesmo tempo.

    Tabela do Web, não do shared: não há entidade correspondente em
    fias-ed-shared/schemas/entities, e por isso ela não carrega o EntityMixin —
    não é um objeto do modelo de dados científico, é a evidência bruta de um
    estágio do pipeline. Sai junto com a transcrição em `apagar_transcricao`."""
    __tablename__ = "trecho_de_fala"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transcricao_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("transcricao.id"), index=True,
                                                      nullable=False)
    inicio_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    fim_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    n_vozes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Segmento(EntityMixin, Base):
    __tablename__ = "segmento"
    transcricao_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("transcricao.id"), index=True,
                                                      nullable=False)
    falante_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("falante.id"), nullable=False)
    start_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    end_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    texto_original_asr: Mapped[str] = mapped_column(String(10000), nullable=False)
    texto_revisado: Mapped[str | None] = mapped_column(String(10000), nullable=True)
    revisado: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    asr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    text_pseudonymized: Mapped[str | None] = mapped_column(String(10000), nullable=True)


class ClassificacaoFIAS(EntityMixin, Base):
    __tablename__ = "classificacao_fias"
    segmento_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("segmento.id"), index=True,
                                                   nullable=False)
    transcript_source: Mapped[str] = mapped_column(
        _enum(TRANSCRIPT_SOURCES, "classificacao_transcript_source"), nullable=False)
    pred_raw: Mapped[int] = mapped_column(Integer, nullable=False)
    pred_role_constrained: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence_raw: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    uncertain: Mapped[bool] = mapped_column(Boolean, nullable=False)
    model_id: Mapped[str] = mapped_column(String, nullable=False)
    rules_version: Mapped[str] = mapped_column(String, nullable=False)


class IndicadorFIAS(EntityMixin, Base):
    __tablename__ = "indicador_fias"
    aula_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("aula.id"), index=True, nullable=False)
    index_id: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    reason: Mapped[str | None] = mapped_column(_enum(INDICADOR_REASONS, "indicador_reason"),
                                               nullable=True)
    numerator_count: Mapped[int] = mapped_column(Integer, nullable=False)
    denominator_count: Mapped[int] = mapped_column(Integer, nullable=False)
    n_intervals: Mapped[int] = mapped_column(Integer, nullable=False)
    rules_version: Mapped[str] = mapped_column(String, nullable=False)
    validation_status: Mapped[str] = mapped_column(
        _enum(VALIDATION_STATUS, "indicador_validation_status"), nullable=False)
    mean_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)


class Ciclo(EntityMixin, Base):
    __tablename__ = "ciclo"
    turma_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("turma.id"), index=True, nullable=False)
    disciplina_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("disciplina.id"), nullable=False)
    professor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("professor.id"), index=True, nullable=False)
    n_aulas_previstas: Mapped[int] = mapped_column(Integer, nullable=False)
    iniciado_em: Mapped[date] = mapped_column(Date, nullable=False)
    encerrado_em: Mapped[date | None] = mapped_column(Date, nullable=True)


ORIGEM_QTI = ("COLETA_NATIVA", "IMPORTACAO_EXTERNA")


class ColetaQTI(EntityMixin, Base):
    __tablename__ = "coleta_qti"
    ciclo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ciclo.id"), index=True, nullable=False)
    coletado_em: Mapped[date] = mapped_column(Date, nullable=False)
    origem: Mapped[str] = mapped_column(_enum(ORIGEM_QTI, "origem_qti"), nullable=False)
    response_count: Mapped[int] = mapped_column(Integer, nullable=False)
    displayable: Mapped[bool] = mapped_column(Boolean, nullable=False)
    qti_config_version: Mapped[str] = mapped_column(String, nullable=False)
    # A linha de cabeçalho exata do arquivo importado (só para origem IMPORTACAO_EXTERNA;
    # nulo para COLETA_NATIVA, que não nasce de um arquivo). O avalie-seu-professor não
    # declara versão de formato no que exporta (checado em app/qti/service.py, que também
    # documenta o que esta coluna NÃO detecta: reordenação de itens sob os mesmos nomes de
    # coluna). Isto é o substituto honesto: duas coletas com cabeçalhos diferentes ficam
    # distinguíveis depois, mesmo sem a importação recusar nenhuma delas.
    cabecalho_recebido: Mapped[str | None] = mapped_column(String, nullable=True)


class RespostaQTI(Base):
    """Sem identidade, por construção. O respondente é um índice sequencial
    dentro da coleta — é o que o formato de exportação do motor espera.

    Não usa EntityMixin: o `device_id` do mixin é a instalação do professor que
    gravou a linha, não o dispositivo do estudante, mas numa tabela por
    respondente esse nome de coluna lê como identidade mesmo sem ser — e nesta
    tabela, a mais sensível da fatia, ambiguidade de nome já é o risco. Os
    demais campos de auditoria e exclusão lógica do mixin são replicados abaixo,
    exceto ele. Mesmo princípio do §48 aplicado à fala: a ausência é o
    mecanismo, não um esquecimento."""
    __tablename__ = "resposta_qti"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow,
                                                 nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, onupdate=literal_column("version + 1"),
                                         nullable=False)
    sync_status: Mapped[str] = mapped_column(_enum(SYNC_STATUS, "sync_status"), default="LOCAL_ONLY",
                                             nullable=False)
    coleta_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("coleta_qti.id"), index=True, nullable=False)
    response_index: Mapped[int] = mapped_column(Integer, nullable=False)
    respostas: Mapped[dict] = mapped_column(JSON, nullable=False)  # {"1": 4, "2": 3, ... "24": 5}


class ResultadoQTI(EntityMixin, Base):
    __tablename__ = "resultado_qti"
    coleta_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("coleta_qti.id"), index=True, nullable=False)
    octantes: Mapped[dict] = mapped_column(JSON, nullable=False)
    agency: Mapped[float] = mapped_column(Float, nullable=False)
    communion: Mapped[float] = mapped_column(Float, nullable=False)


class LinkQTI(Base):
    """O segredo do link nunca é gravado — só o hash. Quem tem o link consegue
    responder; quem tem o banco, não consegue reconstruí-lo.

    Não usa EntityMixin: replica os campos de auditoria à mão, sem
    `device_id`, mesmo padrão de `RespostaQTI`. `LinkQTI` sozinha seria
    artefato do professor autenticado — `device_id` aqui significaria a
    instalação dele, e seria honesto. Mesmo assim uniformizamos com
    `ConsentimentoQTI` e `RespostaQTI`, que precisam da ausência por serem
    tocadas pelo estudante: "nas três tabelas da coleta nativa não existe
    device_id" é uma frase que qualquer auditoria de privacidade verifica em
    segundos; "existe numa e não nas outras duas" exige reconstruir o
    raciocínio tabela por tabela. A procedência de LinkQTI já está na
    cadeia (coleta → ciclo → professor); perder qual instalação gerou cada
    link, num sistema de uso local e single-user, é custo aceito."""
    __tablename__ = "link_qti"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow,
                                                 nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, onupdate=literal_column("version + 1"),
                                         nullable=False)
    sync_status: Mapped[str] = mapped_column(_enum(SYNC_STATUS, "sync_status"), default="LOCAL_ONLY",
                                             nullable=False)
    coleta_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("coleta_qti.id"), index=True, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expira_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    limite_respostas: Mapped[int] = mapped_column(Integer, nullable=False)
    revogado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ConsentimentoQTI(Base):
    """Uma linha por COLETA, não por estudante. Registra QUE houve
    consentimento e sob qual versão do documento — nunca quem, nem quando
    cada um consentiu. `aceites` é um contador, incrementado a cada
    consentimento; não é um carimbo de tempo individual.

    O carimbo individual foi cogitado (`aceito_em`) e descartado: no fluxo
    real o consentimento antecede a resposta por poucos segundos, e numa
    turma de trinta, ordenar `consentimento_qti` e `resposta_qti` por tempo e
    parear vizinhos reconstruiria o vínculo que o §7 proíbe — sem chave
    estrangeira, sem índice de respondente, sem nome suspeito, só relógio.
    Uma linha por coleta fecha esse canal: sem linha por estudante, não há o
    que parear. Mesmo princípio do §48 que proíbe agrupar voz por estudante.

    `coleta_id` é `unique=True`: "uma linha por coleta" é uma garantia de
    banco, não de boa vontade de quem chamar. Sem essa restrição, duas
    respostas chegando ao mesmo tempo poderiam fazer busca-ou-cria em
    paralelo, ambas encontrarem vazio, ambas inserirem — e aí a coleta
    voltaria a ter estrutura por evento, reabrindo o pareamento que a
    linha única existe para fechar.

    Não usa EntityMixin, pelo mesmo motivo de `RespostaQTI`: `device_id` do
    mixin é a instalação do professor, não do estudante, e aqui — um ato do
    estudante — o nome mentiria. Ver o docstring de `LinkQTI` para por que
    a ausência é uniforme nas três tabelas da coleta nativa."""
    __tablename__ = "consentimento_qti"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow,
                                                 nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, onupdate=literal_column("version + 1"),
                                         nullable=False)
    sync_status: Mapped[str] = mapped_column(_enum(SYNC_STATUS, "sync_status"), default="LOCAL_ONLY",
                                             nullable=False)
    coleta_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("coleta_qti.id"), unique=True, nullable=False)
    documento_versao: Mapped[str] = mapped_column(String(32), nullable=False)
    aceites: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


TRIANGULACAO_FIAS_KIND = ("index", "categories")


class Triangulacao(EntityMixin, Base):
    """Um par (evidência do FIAS, percepção do QTI) por aula, para cada linha
    de `pedagogical_rules.triangulation_pairs`. Nenhum campo aqui nasce de uma
    conta feita neste módulo: tudo vem de `fias_ed_engine.triangulation.
    triangulate`, que também escreve `validation_status` sempre como
    PENDING_SCIENTIFIC_VALIDATION — a triangulação justapõe evidências, não
    julga o professor."""
    __tablename__ = "triangulacao"
    aula_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("aula.id"), index=True, nullable=False)
    pair_id: Mapped[str] = mapped_column(String, nullable=False)
    fias_kind: Mapped[str] = mapped_column(_enum(TRIANGULACAO_FIAS_KIND, "triangulacao_fias_kind"),
                                           nullable=False)
    # string quando fias_kind="index" (o id do índice), lista quando "categories"
    # (as categorias FIAS somadas) — o motor decide qual é qual, não esta coluna.
    fias_ref: Mapped[str | list] = mapped_column(JSON, nullable=False)
    fias_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    qti_available: Mapped[bool] = mapped_column(Boolean, nullable=False)
    qti_values: Mapped[list] = mapped_column(JSON, nullable=False)
    reflection_question: Mapped[str] = mapped_column(String, nullable=False)
    source_reference: Mapped[str] = mapped_column(String, nullable=False)
    validation_status: Mapped[str] = mapped_column(
        _enum(VALIDATION_STATUS, "triangulacao_validation_status"), nullable=False)


MTSS_QTI_AGREEMENT = ("agree", "disagree", "inconclusive", "unpaired", "no_qti")


class InterpretacaoMTSS(EntityMixin, Base):
    """Uma linha por regra do MTSS Tier 1 disparada pela aula, já qualificada
    à luz do QTI. Nenhum campo aqui nasce de uma conta feita neste módulo:
    `fias_ed_engine.mtss.evaluate` decide o que dispara, `interpretation` e
    `framing` vêm dele, e `qualify` decide `qti_agreement` — inclusive
    `unpaired` (regra sem par de triangulação) e `no_qti` (aula sem coleta
    vigente), que não são erro: o MTSS nunca dependeu do QTI para disparar.
    `validation_status` chega sempre PENDING_SCIENTIFIC_VALIDATION — mesma
    honestidade científica declarada de `Triangulacao`."""
    __tablename__ = "interpretacao_mtss"
    aula_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("aula.id"), index=True, nullable=False)
    rule_id: Mapped[str] = mapped_column(String, nullable=False)
    tier1_dimension: Mapped[str] = mapped_column(String, nullable=False)
    framing: Mapped[str] = mapped_column(String, nullable=False)
    interpretation: Mapped[str] = mapped_column(String, nullable=False)
    evidence: Mapped[dict] = mapped_column(JSON, nullable=False)
    evidence_segment_categories: Mapped[list] = mapped_column(JSON, nullable=False)
    source_reference: Mapped[str] = mapped_column(String, nullable=False)
    validation_status: Mapped[str] = mapped_column(
        _enum(VALIDATION_STATUS, "interpretacao_mtss_validation_status"), nullable=False)
    rules_version: Mapped[str] = mapped_column(String, nullable=False)
    qti_agreement: Mapped[str] = mapped_column(
        _enum(MTSS_QTI_AGREEMENT, "interpretacao_mtss_qti_agreement"), nullable=False)
    qti_evidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    divergence_question: Mapped[str | None] = mapped_column(String, nullable=True)


class RecomendacaoMTSS(EntityMixin, Base):
    """Uma linha por recomendação pedagógica disparada pela aula — enquadrada
    como reflexão, nunca como correção do professor (spec do MTSS).
    `qti_agreement` é cópia deliberada do campo da regra que originou a
    recomendação (`rule_id`): a tela (Task 11) precisa dele para ordenar as
    recomendações concordantes primeiro sem cruzar com `interpretacao_mtss`.
    Nada aqui é reordenado nem pontuado — a ordem gravada é a que o motor
    devolveu."""
    __tablename__ = "recomendacao_mtss"
    aula_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("aula.id"), index=True, nullable=False)
    recommendation_id: Mapped[str] = mapped_column(String, nullable=False)
    rule_id: Mapped[str] = mapped_column(String, nullable=False)
    text: Mapped[str] = mapped_column(String, nullable=False)
    validation_status: Mapped[str] = mapped_column(
        _enum(VALIDATION_STATUS, "recomendacao_mtss_validation_status"), nullable=False)
    source_reference: Mapped[str] = mapped_column(String, nullable=False)
    qti_agreement: Mapped[str] = mapped_column(
        _enum(MTSS_QTI_AGREEMENT, "recomendacao_mtss_qti_agreement"), nullable=False)


class ModeloIA(EntityMixin, Base):
    __tablename__ = "modelo_ia"
    model_id: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    model_version: Mapped[str] = mapped_column(String, nullable=False)
    task: Mapped[str] = mapped_column(String, nullable=False)
    format: Mapped[str] = mapped_column(_enum(MODEL_FORMATS, "modelo_format"), nullable=False)
    sha256: Mapped[str] = mapped_column(String, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source: Mapped[str] = mapped_column(String(500), nullable=False)
    license: Mapped[str] = mapped_column(String(200), nullable=False)
    parameters: Mapped[dict] = mapped_column(JSONB, nullable=False)


class Processamento(EntityMixin, Base):
    """Criada em W1 para manter o modelo completo; primeira linha nasce no W2."""
    __tablename__ = "processamento"
    aula_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("aula.id"), index=True, nullable=False)
    app_version: Mapped[str] = mapped_column(String, nullable=False)
    rules_version: Mapped[str] = mapped_column(String, nullable=False)
    asr_model: Mapped[str] = mapped_column(String, nullable=False)
    asr_model_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    diarization_model: Mapped[str] = mapped_column(String, nullable=False)
    fias_model: Mapped[str] = mapped_column(String, nullable=False)
    fias_model_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    parameters: Mapped[dict] = mapped_column(JSONB, nullable=False)
    hardware: Mapped[str] = mapped_column(String(200), nullable=False)
    device: Mapped[str] = mapped_column(String(200), nullable=False)
    audio_duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    transcript_source: Mapped[str] = mapped_column(_enum(TRANSCRIPT_SOURCES, "transcript_source"), nullable=False)
    stage_times_ms: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(_enum(AULA_STATUS, "processamento_status"), nullable=False)
    processing_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    role_divergence_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)


# ---- Tabelas internas (fora do modelo lógico compartilhado; nunca exportadas) ----

class Sessao(Base):
    __tablename__ = "sessao"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    professor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("professor.id"), index=True, nullable=False)
    acting_as_professor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("professor.id"), nullable=True)
    token_sha256: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    csrf_token_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AudioUpload(Base):
    """Áudio recebido e ainda não validado (dados do schema Audio só existem após o ffprobe)."""
    __tablename__ = "audio_upload"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    aula_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("aula.id"), unique=True, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    internal_filename: Mapped[str] = mapped_column(String(64), nullable=False)
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Job(Base):
    __tablename__ = "job"
    __table_args__ = (Index("ix_job_status_created", "status", "created_at"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    aula_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("aula.id"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(_enum(JOB_STATUS, "job_status"), default="queued", nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AcessoAdmin(Base):
    __tablename__ = "acesso_admin"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    admin_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("professor.id"), nullable=False)
    professor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("professor.id"), index=True, nullable=True)
    resource: Mapped[str] = mapped_column(String(32), nullable=False)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True, nullable=True)
    action: Mapped[str] = mapped_column(_enum(ADMIN_ACTIONS, "admin_action"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
