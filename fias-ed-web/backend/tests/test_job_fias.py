"""Task 12: job de classificação FIAS.

Nenhuma regra científica é testada aqui de novo — isso já é coberto pelos
vetores de conformance do fias_ed_engine. O que este arquivo prova é que o
Web produz (segmento, logits, papel) corretamente, persiste exatamente o que
`constrain_by_role` devolveu (crua e restrita, sem descartar nada) e grava um
Processamento reprodutível.

ClassificacaoFIAS não tem coluna `aula_id` (só `segmento_id`) e não tem coluna
`categoria` (só `pred_raw`/`pred_role_constrained`) — os helpers abaixo usam os
nomes reais de app/models.py.
"""
import uuid

import pytest
from sqlalchemy import select

from app.fias import service as fias_service
from app.jobs.handlers import HANDLERS
from app.jobs.queue import enqueue
from app.core.config import get_settings
from app.ml.fakes import ClassificadorFalso
from app.ml.registry import carregar_registro, entrada
from app.models import (Audio, ClassificacaoFIAS, Falante, IndicadorFIAS, Job, ModeloIA, Processamento,
                        Segmento, Transcricao, TrechoDeFala)
from tests.helpers import login, make_aula, make_user


def _construir_aula(db, username: str, *, status: str, segmentos_spec: list[tuple[str, str, bool]]):
    """segmentos_spec: lista de (papel, texto, revisado). `revisado=True` grava
    texto_revisado igual ao original (o professor confirmou o trecho); `False`
    deixa texto_revisado nulo, para texto_efetivo cair no bruto do ASR."""
    prof = make_user(db, username)
    aula = make_aula(db, prof, status=status)
    audio = Audio(aula_id=aula.id, original_filename="aula.wav", internal_filename=f"{uuid.uuid4()}.wav",
                 path="original/aula.wav", mime_type="audio/wav", size_bytes=1,
                 duration_ms=len(segmentos_spec) * 3_000, sha256="0" * 64, channels=1, sample_rate=16000,
                 is_original=True, derived_from_audio_id=None)
    db.add(audio)
    db.flush()
    transcricao = Transcricao(aula_id=aula.id, audio_id=audio.id, asr_model_id="fake-asr")
    db.add(transcricao)
    db.flush()
    falantes = {
        "PROFESSOR": Falante(transcricao_id=transcricao.id, diarization_label="SPEAKER_00", role="PROFESSOR"),
        "ALUNO": Falante(transcricao_id=transcricao.id, diarization_label="merged", role="ALUNO"),
    }
    db.add_all(falantes.values())
    db.flush()
    for i, (papel, texto, revisado) in enumerate(segmentos_spec):
        db.add(Segmento(transcricao_id=transcricao.id, falante_id=falantes[papel].id, start_ms=i * 3_000,
                        end_ms=(i + 1) * 3_000, texto_original_asr=texto,
                        texto_revisado=texto if revisado else None, revisado=revisado))
    db.commit()
    return aula


@pytest.fixture
def aula_revisada(db):
    """Aula pronta para classificar, toda revisada: duas falas do professor e
    uma do aluno, para exercitar os dois papéis."""
    return _construir_aula(db, "carla-fias", status="READY_FOR_FIAS", segmentos_spec=[
        ("PROFESSOR", "a professora explica a questão", True),
        ("ALUNO", "o aluno responde a pergunta", True),
        ("PROFESSOR", "a professora faz outra pergunta", True),
    ])


@pytest.fixture
def aula_revisada_parcialmente(db):
    """Um trecho revisado, outro ainda cru — prova que transcript_source é por
    segmento, não um valor único para a aula inteira."""
    return _construir_aula(db, "bruna-fias", status="READY_FOR_FIAS", segmentos_spec=[
        ("PROFESSOR", "a professora explica a questão", True),
        ("ALUNO", "o aluno responde a pergunta", False),
    ])


@pytest.fixture
def classificador_falso(monkeypatch):
    """Categoria docente qualquer (5): não força 8/9, então serve de cenário
    neutro para os testes que não checam a restrição por papel."""
    clf = ClassificadorFalso(categoria_fixa=5)
    monkeypatch.setattr(fias_service, "obter_classificador", lambda: clf)
    return clf


@pytest.fixture
def classificador_falso_categoria_8(monkeypatch):
    """O modelo sempre "diz" categoria 8 (fala de aluno) — inclusive para
    segmentos do professor, para provar que constrain_by_role corrige."""
    clf = ClassificadorFalso(categoria_fixa=8)
    monkeypatch.setattr(fias_service, "obter_classificador", lambda: clf)
    return clf


@pytest.fixture
def classificador_falso_indeciso(monkeypatch):
    """Vetor uniforme: nenhuma categoria domina, a confiança fica abaixo do
    limiar do shared (uncertain_below) para qualquer papel."""
    clf = ClassificadorFalso(categoria_fixa=None)
    monkeypatch.setattr(fias_service, "obter_classificador", lambda: clf)
    return clf


@pytest.fixture
def aula_classificada(db, classificador_falso):
    """Uma aula que já passou pela classificação uma vez — o cenário de
    reclassificação (spec §3: editar depois de FIAS_COMPLETED reabre e
    reclassifica; evidência e resultado não podem ficar fora de sincronia).

    Chama `classificar_aula` direto (não passa pela fila) de propósito: esta
    fixture é estado ("a aula já foi classificada"), não um teste do job em si
    — isso já é coberto por `_rodar`/HANDLERS nos testes que exercitam o job.
    Passar pela fila aqui deixaria um Job "done" de bônus, o que quebraria
    `test_reabrir_a_revisao_nao_enfileira` (que checa contagem zero de Job)."""
    aula = _construir_aula(db, "diana-fias", status="READY_FOR_FIAS", segmentos_spec=[
        ("PROFESSOR", "a professora explica a questão", True),
        ("ALUNO", "o aluno responde a pergunta", True),
    ])
    fias_service.classificar_aula(db, aula)
    aula.status, aula.error_code = "FIAS_COMPLETED", None
    db.commit()
    return aula


@pytest.fixture
def aula_em_revisao(db):
    """Em READY_FOR_TRANSCRIPT_REVIEW — o status que `POST
    /transcricao/concluir` exige antes de avançar."""
    return _construir_aula(db, "elisa-fias", status="READY_FOR_TRANSCRIPT_REVIEW", segmentos_spec=[
        ("PROFESSOR", "a professora explica a questão", True),
    ])


def _rodar(db, aula):
    job = enqueue(db, aula.id, "classify_fias")
    db.commit()
    HANDLERS["classify_fias"](db, job)


def contar_segmentos(db, aula) -> int:
    transcricao = db.scalar(select(Transcricao).where(Transcricao.aula_id == aula.id))
    return db.query(Segmento).filter_by(transcricao_id=transcricao.id).count()


def classificacoes_de(db, aula) -> list[ClassificacaoFIAS]:
    return (db.query(ClassificacaoFIAS)
           .join(Segmento, Segmento.id == ClassificacaoFIAS.segmento_id)
           .join(Transcricao, Transcricao.id == Segmento.transcricao_id)
           .filter(Transcricao.aula_id == aula.id).all())


def classificacoes_de_papel(db, aula, papel: str) -> list[ClassificacaoFIAS]:
    return (db.query(ClassificacaoFIAS)
           .join(Segmento, Segmento.id == ClassificacaoFIAS.segmento_id)
           .join(Falante, Falante.id == Segmento.falante_id)
           .join(Transcricao, Transcricao.id == Segmento.transcricao_id)
           .filter(Transcricao.aula_id == aula.id, Falante.role == papel).all())


def primeiro_segmento(db, aula) -> Segmento:
    return (db.query(Segmento).join(Transcricao, Transcricao.id == Segmento.transcricao_id)
           .filter(Transcricao.aula_id == aula.id).order_by(Segmento.start_ms).first())


# ---- Rodada de conserto 1: alguém precisa enfileirar classify_fias ----
#
# Todo teste acima enfileira o job à mão (via `_rodar`/enqueue direto), então a
# suíte inteira ficava verde enquanto nenhum caminho de produção disparava a
# classificação — a aula parava em READY_FOR_FIAS para sempre. Os dois testes
# abaixo travam a costura: concluir a revisão enfileira; reabrir não.


def test_concluir_a_revisao_enfileira_a_classificacao(client, db, aula_em_revisao):
    """Sem isto a aula para em READY_FOR_FIAS para sempre, e a suíte não percebe
    porque todo teste desta task enfileira o job à mão."""
    login(client, "elisa-fias")
    r = client.post(f"/api/aulas/{aula_em_revisao.id}/transcricao/concluir")
    assert r.status_code == 200
    assert db.query(Job).filter_by(aula_id=aula_em_revisao.id, type="classify_fias").count() == 1


def test_reabrir_a_revisao_nao_enfileira(client, db, aula_classificada):
    """Cinquenta trechos corrigidos não podem virar cinquenta classificações."""
    login(client, "diana-fias")
    seg = primeiro_segmento(db, aula_classificada)
    r = client.patch(f"/api/segmentos/{seg.id}", json={"texto": "a", "version": seg.version})
    assert r.status_code == 200
    db.refresh(aula_classificada)
    assert aula_classificada.status == "READY_FOR_FIAS"
    assert db.query(Job).filter_by(aula_id=aula_classificada.id, type="classify_fias").count() == 0


# ---- Steps 1-4: o job em si ----


def test_classificacao_grava_uma_linha_por_segmento(db, aula_revisada, classificador_falso):
    _rodar(db, aula_revisada)
    n_segmentos = contar_segmentos(db, aula_revisada)
    assert len(classificacoes_de(db, aula_revisada)) == n_segmentos


def test_o_contexto_enviado_ao_modelo_segue_o_papel_do_falante(db, aula_revisada, classificador_falso):
    """A ponta do conserto que os testes de `montar_pares` não alcançam: o papel
    tem de sair do banco e chegar à montagem do par.

    A fixture é PROFESSOR → ALUNO → PROFESSOR, três trocas de falante seguidas,
    então os três pares carregam contexto — menos o primeiro, que não tem turno
    anterior. Fixa QUAL texto foi para o `text_a` de cada um: contar vazios
    passaria com o par montado ao contrário."""
    fias_service.classificar_aula(db, aula_revisada)
    assert classificador_falso.pares_recebidos == [
        ("", "a professora explica a questão"),
        ("a professora explica a questão", "o aluno responde a pergunta"),
        ("o aluno responde a pergunta", "a professora faz outra pergunta"),
    ]


def test_falas_seguidas_do_mesmo_papel_vao_sem_contexto(db, classificador_falso):
    """O outro lado da mesma regra, ponta a ponta: dois segmentos do professor
    em sequência (o caso comum de uma aula expositiva, e o que a produção
    classificava errado) não podem levar o segmento anterior como contexto."""
    aula = _construir_aula(db, "elisa-fias", status="READY_FOR_FIAS", segmentos_spec=[
        ("PROFESSOR", "a professora começa a explicação", True),
        ("PROFESSOR", "a professora continua explicando", True),
        ("ALUNO", "o aluno faz uma pergunta", True),
    ])
    fias_service.classificar_aula(db, aula)
    assert classificador_falso.pares_recebidos == [
        ("", "a professora começa a explicação"),
        ("", "a professora continua explicando"),
        ("a professora continua explicando", "o aluno faz uma pergunta"),
    ]


def test_indices_sao_gravados_com_evidencia_e_rules_version(db, aula_revisada, classificador_falso):
    _rodar(db, aula_revisada)
    indicadores = db.query(IndicadorFIAS).filter_by(aula_id=aula_revisada.id).all()
    assert indicadores
    # A evidência do shared é estruturada, não um JSONB livre.
    assert all(i.numerator_count is not None for i in indicadores)
    assert all(i.denominator_count is not None for i in indicadores)
    assert all(i.n_intervals > 0 for i in indicadores)
    assert all(i.validation_status for i in indicadores)
    assert all(i.rules_version for i in indicadores)


def test_classificacao_leva_a_fias_completed(db, aula_revisada, classificador_falso):
    _rodar(db, aula_revisada)
    db.refresh(aula_revisada)
    assert aula_revisada.status == "FIAS_COMPLETED"


def test_guarda_a_predicao_crua_e_a_restrita_por_papel(db, aula_revisada, classificador_falso_categoria_8):
    """As duas colunas existem para rastreabilidade: o que o modelo disse, e o
    que sobrou depois da restrição por papel. Guardar só a segunda apagaria a
    evidência de que houve restrição."""
    _rodar(db, aula_revisada)
    de_aluno = classificacoes_de_papel(db, aula_revisada, "ALUNO")
    assert de_aluno
    assert all(c.pred_raw == 8 for c in de_aluno)          # o que o modelo disse
    assert all(c.pred_role_constrained in (8, 9) for c in de_aluno)
    assert all(c.confidence_raw > 0 and c.confidence > 0 for c in de_aluno)


def test_marca_uncertain_abaixo_do_limiar_do_shared(db, aula_revisada, classificador_falso_indeciso):
    """uncertain_below está em fias_rules.classifier; quem decide é o motor."""
    _rodar(db, aula_revisada)
    assert any(c.uncertain for c in classificacoes_de(db, aula_revisada))


def test_transcript_source_reflete_se_o_professor_revisou(db, aula_revisada_parcialmente, classificador_falso):
    _rodar(db, aula_revisada_parcialmente)
    fontes = {c.transcript_source for c in classificacoes_de(db, aula_revisada_parcialmente)}
    assert fontes == {"ASR_ORIGINAL", "TRANSCRICAO_REVISADA"}


def test_a_categoria_respeita_o_papel_do_falante(db, aula_revisada, classificador_falso_categoria_8):
    """constrain_by_role é do motor do shared: uma categoria de fala docente num
    segmento de ALUNO tem de ser corrigida antes de virar intervalo — e o
    inverso também: aqui o modelo "diz" 8 (categoria de aluno) para TODO
    segmento, então nos segmentos de PROFESSOR isso é inválido e precisa ser
    remapeado para 1-7. Checar só o lado ALUNO seria fraco demais: categoria 8
    já é válida para ALUNO mesmo que constrain_by_role não fizesse nada."""
    _rodar(db, aula_revisada)
    de_aluno = classificacoes_de_papel(db, aula_revisada, "ALUNO")
    de_professor = classificacoes_de_papel(db, aula_revisada, "PROFESSOR")
    assert de_aluno and de_professor
    assert all(c.pred_role_constrained in (8, 9) for c in de_aluno)
    assert all(c.pred_raw == 8 for c in de_professor)  # o modelo "disse" 8 mesmo assim
    assert all(c.pred_role_constrained in range(1, 8) for c in de_professor)
    assert all(c.pred_role_constrained != c.pred_raw for c in de_professor)  # a restrição de fato corrigiu


def test_reclassificar_apaga_o_resultado_anterior(db, aula_classificada, classificador_falso):
    antes = len(classificacoes_de(db, aula_classificada))
    _rodar(db, aula_classificada)
    depois = len(classificacoes_de(db, aula_classificada))
    assert depois == antes  # não duplicou


def test_job_para_aula_excluida_e_fechado_sem_classificar(db, aula_revisada, classificador_falso):
    from app.models import utcnow
    aula_revisada.deleted_at = utcnow()
    db.commit()
    job = enqueue(db, aula_revisada.id, "classify_fias")
    db.commit()
    HANDLERS["classify_fias"](db, job)
    db.refresh(job)
    assert job.status == "done"
    assert classificacoes_de(db, aula_revisada) == []


# ---- Step 5: Processamento reprodutível ----


def test_processamento_registra_modelo_parametros_e_versoes(db, aula_revisada, classificador_falso):
    """Os nomes de coluna são os da tabela criada na W1 (app/models.py), não
    inventados aqui: asr_model, asr_model_hash, diarization_model, fias_model,
    fias_model_hash, parameters."""
    _rodar(db, aula_revisada)
    proc = db.query(Processamento).filter_by(aula_id=aula_revisada.id).one()
    assert proc.asr_model and proc.asr_model_hash
    assert proc.diarization_model
    assert proc.fias_model and proc.fias_model_hash
    assert proc.app_version and proc.rules_version
    assert proc.parameters["asr"]["temperature"] == 0.0
    assert proc.parameters["asr"]["language"] == "pt"


def test_processamento_preenche_todas_as_colunas_obrigatorias(db, aula_revisada, classificador_falso):
    """A tabela da W1 tem quinze colunas NOT NULL; nenhuma pode ficar de fora,
    ou o INSERT falha em produção e não no teste, se o teste não a exercitar."""
    _rodar(db, aula_revisada)
    proc = db.query(Processamento).filter_by(aula_id=aula_revisada.id).one()
    assert proc.hardware and proc.device
    assert proc.audio_duration_ms > 0
    assert proc.transcript_source in ("ASR_ORIGINAL", "TRANSCRICAO_REVISADA")
    assert proc.stage_times_ms
    assert proc.status == "FIAS_COMPLETED"


def test_modelo_ia_nasce_do_registro_do_shared(db, aula_revisada, classificador_falso):
    _rodar(db, aula_revisada)
    m = db.query(ModeloIA).filter_by(task="fias_utterance_classification").one()
    do_registro = entrada(get_settings().clf_model_id)
    assert m.model_id == do_registro["model_id"]
    assert m.model_version == carregar_registro()["registry_version"]
    # o SHA-256 vem do registro, não de uma lista local
    assert m.sha256 == next(a["sha256"] for a in do_registro["artifacts"] if a["role"] == "weights")


def test_reprocessar_nao_duplica_o_processamento(db, aula_classificada, classificador_falso):
    _rodar(db, aula_classificada)
    assert db.query(Processamento).filter_by(aula_id=aula_classificada.id).count() == 1
    assert db.query(ModeloIA).filter_by(task="fias_utterance_classification").count() == 1


# ---- Categoria 10: o trecho que o ASR não transcreveu não é silêncio ----------
#
# app/ml/asr_whisper.py descarta o segmento sem texto (`if s.text.strip()`). O
# descarte é silencioso, e o que ele deixa para trás é uma lacuna entre
# segmentos do ASR — exatamente a forma de um silêncio, se alguém medisse
# silêncio por aí. Medir por aí é o pior erro possível nesta categoria: o
# trecho em que o diarizador ouviu voz e o Whisper não produziu texto é
# candidato a CONFUSÃO, que é o oposto acústico de silêncio.


def _aula_com_buraco_de_transcricao(db):
    """Nove segundos de aula em que o diarizador ouviu voz o tempo todo, mas o
    ASR só produziu texto nos três primeiros e nos três últimos. O buraco tem
    exatamente 3 000 ms: é o limiar da regra 4, de propósito — meio milissegundo
    a menos e o teste passaria mesmo com a medição errada."""
    prof = make_user(db, "flavia-fias")
    aula = make_aula(db, prof, status="READY_FOR_FIAS")
    audio = Audio(aula_id=aula.id, original_filename="aula.wav", internal_filename=f"{uuid.uuid4()}.wav",
                  path="original/aula.wav", mime_type="audio/wav", size_bytes=1, duration_ms=9_000,
                  sha256="0" * 64, channels=1, sample_rate=16000, is_original=True,
                  derived_from_audio_id=None)
    db.add(audio)
    db.flush()
    transcricao = Transcricao(aula_id=aula.id, audio_id=audio.id, asr_model_id="fake-asr")
    db.add(transcricao)
    db.flush()
    falante = Falante(transcricao_id=transcricao.id, diarization_label="SPEAKER_00", role="PROFESSOR")
    db.add(falante)
    db.flush()
    for inicio, fim in ((0, 3_000), (6_000, 9_000)):
        db.add(Segmento(transcricao_id=transcricao.id, falante_id=falante.id, start_ms=inicio,
                        end_ms=fim, texto_original_asr="a professora explica a questão",
                        texto_revisado=None, revisado=False))
    # A evidência de fala do separador de vozes cobre a aula inteira, inclusive
    # o buraco: houve voz ali, o ASR é que não produziu texto.
    db.add(TrechoDeFala(transcricao_id=transcricao.id, inicio_ms=0, fim_ms=9_000, n_vozes=1))
    db.commit()
    return aula


def test_segmento_sem_texto_nunca_vira_silencio(db, classificador_falso):
    """Ponta a ponta, do que o ASR devolveu ao indicador gravado: o buraco de
    3 s é absorvido pela categoria em curso, não marcado como categoria 10. Se
    a classificação deixar de passar a fala do diarizador ao motor, o motor cai
    nas lacunas entre segmentos e este buraco vira silêncio — que é o que este
    teste existe para impedir."""
    aula = _aula_com_buraco_de_transcricao(db)
    _rodar(db, aula)
    sc = db.query(IndicadorFIAS).filter_by(aula_id=aula.id, index_id="SC").one()
    assert sc.n_intervals == 3, "nove segundos de aula, três marcas de 3 s"
    assert sc.numerator_count == 0, "o buraco de transcrição foi contado como silêncio"
    assert sc.value == 0.0
