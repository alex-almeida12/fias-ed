"""Task 10: GET /api/aulas/{id}/relatorio — a porta de saída única do que o
FIAS-ED produziu sobre uma aula: o que a observação mediu (índices), a
triangulação contra a percepção dos estudantes e as recomendações do MTSS.

A prova mais importante desta suíte é `test_relatorio_nao_recalcula`: a rota
só lê `Triangulacao`/`InterpretacaoMTSS`/`RecomendacaoMTSS` já gravadas por
`avancar` — duas chamadas seguidas não podem mudar quantas linhas existem.
"""
import json

import pytest
from sqlalchemy import select

from app.models import InterpretacaoMTSS, RecomendacaoMTSS, Triangulacao
from app.pipeline.estados import avancar
from tests.helpers import login, make_user


@pytest.fixture
def cliente(client_factory, professor):
    c = client_factory()
    login(c, professor.username)
    return c


@pytest.fixture
def aula_report_ready(db, ciclo, coleta_em, aula_classificada):
    """`aula_classificada` (conftest.py raiz) já está em FIAS_COMPLETED,
    ligada ao ciclo da fixture `ciclo` (fixtures são cacheadas por teste,
    então é o mesmo ciclo — docstring de `aula_classificada` descreve
    exatamente este uso). É a única aula do ciclo, ainda não encerrado, na
    data 2026-09-22: `posicao_no_ciclo` a vê como "primeira", e sem coleta
    vigente `avancar` pararia em WAITING_QTI em vez de seguir. A coleta
    abaixo, datada antes da aula, é o que deixa `avancar` seguir pelo
    caminho real de produção (triangular + interpretar) até REPORT_READY.

    Não força `status = "REPORT_READY"` à mão: isso produziria uma aula sem
    Triangulacao nem InterpretacaoMTSS gravadas, e os testes passariam sobre
    um relatório vazio."""
    coleta_em(ciclo, "2026-09-01")
    avancar(db, aula_classificada)
    db.refresh(aula_classificada)
    assert aula_classificada.status == "REPORT_READY"
    return aula_classificada


def test_aula_pronta_traz_as_cinco_chaves(cliente, aula_report_ready):
    r = cliente.get(f"/api/aulas/{aula_report_ready.id}/relatorio")
    assert r.status_code == 200
    corpo = r.json()
    assert set(corpo) == {"aula", "indices", "triangulacao", "interpretacoes", "recomendacoes"}
    assert len(corpo["triangulacao"]) == 4
    assert corpo["indices"]
    assert corpo["recomendacoes"]


def test_aula_que_ainda_nao_chegou_da_409_com_mensagem_do_que_falta(cliente, aula_classificada):
    # aula_classificada para em FIAS_COMPLETED — nunca passou por avancar.
    r = cliente.get(f"/api/aulas/{aula_classificada.id}/relatorio")
    assert r.status_code == 409
    corpo = r.json()
    assert corpo["error_code"] == "AULA_STATE"
    assert corpo["message"]  # mensagem não genérica vazia


def test_aula_esperando_qti_diz_isso_na_mensagem_especifica(db, cliente, aula_classificada):
    """spec do brief: WAITING_QTI precisa de uma mensagem própria, não o
    texto genérico de "ainda processando" — é a única espera que depende de
    uma ação de fora do professor (a coleta do questionário da turma)."""
    avancar(db, aula_classificada)  # sem coleta vigente: para em WAITING_QTI
    db.refresh(aula_classificada)
    assert aula_classificada.status == "WAITING_QTI"

    r = cliente.get(f"/api/aulas/{aula_classificada.id}/relatorio")
    assert r.status_code == 409
    assert "questionário" in r.json()["message"].lower()


def test_aula_de_outro_professor_da_404(client_factory, db, aula_report_ready):
    make_user(db, "outro-professor-relatorio")
    outro = client_factory()
    login(outro, "outro-professor-relatorio")
    r = outro.get(f"/api/aulas/{aula_report_ready.id}/relatorio")
    assert r.status_code == 404


def test_relatorio_nao_recalcula(db, cliente, aula_report_ready):
    """O teste mais importante da tarefa: duas leituras seguidas do relatório
    não podem mudar as linhas de Triangulacao/InterpretacaoMTSS que já
    existem — a rota só lê o que `avancar` já gravou, nunca chama
    `triangular` ou `interpretar` de novo.

    Comparar só a CONTAGEM não basta: `triangular` sempre grava exatamente 4
    pares (um por `pedagogical_rules.triangulation_pairs`), então apagar e
    regravar por baixo dos panos deixaria a contagem intacta (4 antes, 4
    depois) mesmo tendo recalculado — a mutação 2 do brief passou batido na
    primeira versão deste teste, que só contava linhas. Por isso o que se
    compara aqui são os `id`s das linhas: `triangular`/`interpretar` apagam e
    recriam via `db.add`, o que sempre gera um `uuid.uuid4()` novo por linha
    (EntityMixin.id, app/models.py) — um `id` que muda entre as duas leituras
    é a prova de recálculo que a contagem sozinha não pega."""
    def _ids():
        db.expire_all()
        tri = db.scalars(select(Triangulacao).where(Triangulacao.aula_id == aula_report_ready.id)).all()
        interp = db.scalars(
            select(InterpretacaoMTSS).where(InterpretacaoMTSS.aula_id == aula_report_ready.id)).all()
        return {t.id for t in tri}, {i.id for i in interp}

    ids_tri_antes, ids_int_antes = _ids()
    assert len(ids_tri_antes) == 4 and ids_int_antes  # sem regra disparada o teste não provaria nada

    assert cliente.get(f"/api/aulas/{aula_report_ready.id}/relatorio").status_code == 200
    assert cliente.get(f"/api/aulas/{aula_report_ready.id}/relatorio").status_code == 200

    ids_tri_depois, ids_int_depois = _ids()
    assert ids_tri_depois == ids_tri_antes
    assert ids_int_depois == ids_int_antes


def test_validation_status_chega_em_todos_os_pares_e_recomendacoes(db, cliente, aula_report_ready):
    """Triangulacao é sempre PENDING_SCIENTIFIC_VALIDATION (docstring do
    modelo, app/models.py) — nenhum par escapa disso. RecomendacaoMTSS não
    tem essa mesma garantia (pedagogical_rules.json grava
    "draft_pending_researcher_review" para as recomendações de hoje, um
    valor de VALIDATION_STATUS diferente e igualmente válido); o que a task
    pede é que o campo chegue ao corpo tal como foi gravado, não que todas
    as recomendações compartilhem o mesmo valor."""
    corpo = cliente.get(f"/api/aulas/{aula_report_ready.id}/relatorio").json()
    assert corpo["triangulacao"]
    assert all(p["validation_status"] == "PENDING_SCIENTIFIC_VALIDATION" for p in corpo["triangulacao"])
    assert corpo["recomendacoes"]
    assert all(rec["validation_status"] for rec in corpo["recomendacoes"])
    gravadas = {r.recommendation_id: r.validation_status for r in db.scalars(
        select(RecomendacaoMTSS).where(RecomendacaoMTSS.aula_id == aula_report_ready.id)).all()}
    assert all(rec["validation_status"] == gravadas[rec["recommendation_id"]] for rec in corpo["recomendacoes"])


def test_evidencias_por_interpretacao(cliente, aula_report_ready):
    """Uma interpretação cujas `evidence_segment_categories` apontam para
    categoria com segmento real (ex. MTSS_EXPOSITIVE_PREDOMINANCE, categoria
    5, docente) traz `evidencias` com segmento_id e trecho. Uma sem categoria
    nenhuma (ex. MTSS_DIRECT_OVER_INDIRECT, que só olha índices agregados)
    sai com lista vazia — normal, não erro."""
    corpo = cliente.get(f"/api/aulas/{aula_report_ready.id}/relatorio").json()
    interpretacoes = {i["rule_id"]: i for i in corpo["interpretacoes"]}
    assert interpretacoes  # a aula do fixture dispara ao menos uma regra

    com_categoria = [i for i in interpretacoes.values() if i["evidence_segment_categories"]]
    assert com_categoria
    for i in com_categoria:
        assert i["evidencias"]
        assert all({"segmento_id", "inicio_ms", "trecho"} <= set(ev) for ev in i["evidencias"])

    sem_categoria = [i for i in interpretacoes.values() if not i["evidence_segment_categories"]]
    assert sem_categoria
    assert all(i["evidencias"] == [] for i in sem_categoria)


def test_corpo_nao_usa_vocabulario_de_veredito(cliente, aula_report_ready):
    corpo = cliente.get(f"/api/aulas/{aula_report_ready.id}/relatorio").json()
    texto = json.dumps(corpo, ensure_ascii=False).lower()
    for proibido in ("avalia", "nota", "desempenho", "ranking"):
        assert proibido not in texto, proibido
