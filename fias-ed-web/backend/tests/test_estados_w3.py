"""Task 9: `avancar` leva a aula de `FIAS_COMPLETED` até `REPORT_READY`,
triangulando com o QTI e interpretando o MTSS pelo caminho — e decide quais
aulas esperam o questionário antes de seguir.

Nenhuma regra científica é testada aqui: `triangular` e `interpretar` já têm
suíte própria (test_triangulacao.py, test_mtss.py). O que importa nesta
suíte é orquestração: quem espera, quem segue direto, em que ordem cada
estado é marcado, e o destravamento de quem ficou parado em `WAITING_QTI`
quando o questionário finalmente chega.
"""
import app.pipeline.estados as estados
import app.qti.service as qti_service
from app.pipeline.estados import avancar
from tests.helpers import login

CABECALHO = "response_id," + ",".join(f"q{i}" for i in range(1, 25))


def _csv(n_linhas, valor=4):
    linhas = [CABECALHO]
    for i in range(n_linhas):
        linhas.append(f"r{i}," + ",".join([str(valor)] * 24))
    return "\n".join(linhas) + "\n"


def _status(db, aula):
    """Releitura do banco: o objeto em memória pode estar com o valor de antes
    do commit de outra sessão (ex.: quando o destravamento roda dentro de uma
    chamada HTTP, em outra transação)."""
    db.refresh(aula)
    return aula.status


def test_primeira_aula_sem_coleta_para_em_waiting_qti(db, ciclo, aula_classificada_em):
    aula = aula_classificada_em(ciclo, "2026-03-02")
    avancar(db, aula)
    assert _status(db, aula) == "WAITING_QTI"


def test_primeira_aula_com_coleta_vigente_segue_ate_report_ready(db, ciclo, coleta_em, aula_classificada_em):
    """Par do teste anterior: sem ele, nada distingue "esperou porque é
    primeira" de "esperou sempre"."""
    coleta_em(ciclo, "2026-03-01")
    aula = aula_classificada_em(ciclo, "2026-03-02")
    avancar(db, aula)
    assert _status(db, aula) == "REPORT_READY"


def test_ultima_aula_de_ciclo_encerrado_sem_coleta_para_em_waiting_qti(db, ciclo, aula_classificada_em, client):
    """`posicao_no_ciclo` só devolve "ultima" depois do encerramento — sem
    encerrar o ciclo esta aula seria "meio", e o teste passaria pelo motivo
    errado. É a ponta mais importante de proteger: é a última aula que fecha
    a comparação de ponta a ponta do ciclo."""
    aula_classificada_em(ciclo, "2026-03-02")            # primeira
    ultima = aula_classificada_em(ciclo, "2026-03-09")   # candidata a "ultima" após o encerramento
    login(client, "professora-ciclo")
    assert client.post(f"/api/ciclos/{ciclo.id}/encerrar").status_code == 200
    # client.post roda em outra sessão: sem isto o identity map desta sessão
    # devolveria o Ciclo com encerrado_em antigo (None) — mesmo motivo da
    # fixture `posicao` em conftest.py.
    db.expire_all()
    avancar(db, ultima)
    assert _status(db, ultima) == "WAITING_QTI"


def test_ultima_aula_de_ciclo_encerrado_com_coleta_vigente_segue_ate_report_ready(
        db, ciclo, aula_classificada_em, coleta_em, client):
    """Par do teste anterior: sem ele, nada distingue "esperou porque é a
    última" de "esperou sempre"."""
    aula_classificada_em(ciclo, "2026-03-02")
    ultima = aula_classificada_em(ciclo, "2026-03-09")
    coleta_em(ciclo, "2026-03-01")
    login(client, "professora-ciclo")
    assert client.post(f"/api/ciclos/{ciclo.id}/encerrar").status_code == 200
    db.expire_all()
    avancar(db, ultima)
    assert _status(db, ultima) == "REPORT_READY"


def test_ciclo_de_uma_aula_encerrado_sem_coleta_para_em_waiting_qti(db, ciclo, aula_classificada_em, client):
    """"primeira_e_ultima" sai de graça do mesmo desenho acima (mesma tupla de
    pontas, mesmas fixtures): ciclo de uma aula só, encerrado. Não escrevo o
    par "com coleta" para este caso — é o mesmo ramo de código que o teste
    acima já prova, e duplicar só encheria a tabela sem cobrir mutação nova."""
    unica = aula_classificada_em(ciclo, "2026-03-02")
    login(client, "professora-ciclo")
    assert client.post(f"/api/ciclos/{ciclo.id}/encerrar").status_code == 200
    db.expire_all()
    avancar(db, unica)
    assert _status(db, unica) == "WAITING_QTI"


def test_aula_do_meio_vai_direto_a_report_ready(db, ciclo, aula_classificada_em):
    aula_classificada_em(ciclo, "2026-03-02")           # primeira: só para a próxima não ser a primeira
    meio = aula_classificada_em(ciclo, "2026-03-09")    # meio: nunca esperou, mesmo sem coleta nenhuma
    avancar(db, meio)
    assert _status(db, meio) == "REPORT_READY"


def test_aula_fora_de_ciclo_vai_direto_a_report_ready(db, aula_avulsa_classificada):
    avancar(db, aula_avulsa_classificada)
    assert _status(db, aula_avulsa_classificada) == "REPORT_READY"


def test_importar_o_relatorio_destrava_as_aulas_paradas(db, ciclo, aula_classificada_em, client, monkeypatch):
    presa = aula_classificada_em(ciclo, "2026-03-02")   # primeira, sem coleta: fica em WAITING_QTI
    avancar(db, presa)
    assert _status(db, presa) == "WAITING_QTI"

    outra = aula_classificada_em(ciclo, "2026-03-09")   # meio: já chegou ao relatório sozinha
    avancar(db, outra)
    assert _status(db, outra) == "REPORT_READY"

    # Espiona quem o destravamento realmente chama, sem deixar de rodar de
    # verdade: só assim dá para provar que a aula que NÃO estava em
    # WAITING_QTI não foi tocada, e não só que o status dela ficou igual (o
    # que aconteceria de qualquer jeito, já que ela já era REPORT_READY).
    chamadas = []
    avancar_de_verdade = qti_service.avancar

    def espiao(db_arg, aula_arg):
        chamadas.append(aula_arg.id)
        avancar_de_verdade(db_arg, aula_arg)

    monkeypatch.setattr(qti_service, "avancar", espiao)

    login(client, "professora-ciclo")
    r = client.post(f"/api/ciclos/{ciclo.id}/qti/importar",
                    files={"arquivo": ("export.csv", _csv(12), "text/csv")},
                    data={"coletado_em": "2026-03-01"})
    assert r.status_code == 201

    assert chamadas == [presa.id]
    assert _status(db, presa) == "REPORT_READY"


def test_cada_estado_e_marcado_pelo_passo_que_o_alcanca(db, ciclo, aula_classificada_em, monkeypatch):
    """O espião de ordem. Lição da W2: um estado marcado pelo passo anterior
    ao que realmente faz o trabalho mente para quem está olhando a tela."""
    aula_classificada_em(ciclo, "2026-03-02")           # primeira: só para a próxima não ser a primeira
    aula = aula_classificada_em(ciclo, "2026-03-09")    # meio: segue direto, sem depender de coleta

    status_ao_chamar_triangular = []
    status_ao_chamar_interpretar = []

    def espiao_triangular(db_arg, aula_arg):
        status_ao_chamar_triangular.append(aula_arg.status)

    def espiao_interpretar(db_arg, aula_arg):
        status_ao_chamar_interpretar.append(aula_arg.status)
        return [], []

    monkeypatch.setattr(estados, "triangular", espiao_triangular)
    monkeypatch.setattr(estados, "interpretar", espiao_interpretar)

    avancar(db, aula)

    assert status_ao_chamar_triangular == ["FIAS_COMPLETED"]
    assert status_ao_chamar_interpretar == ["TRIANGULATED"]
    assert _status(db, aula) == "REPORT_READY"
