import datetime as dt

import pytest
from sqlalchemy import event, inspect
from sqlalchemy.exc import IntegrityError

from app.core.db import SessionLocal, get_engine
from app.core.errors import AppError
from app.models import ColetaQTI, ResultadoQTI, RespostaQTI
from app.qti.service import coleta_nativa_do_dia
import app.qti.service as qti_service


def _coleta(ciclo, data, **extra):
    return ColetaQTI(ciclo_id=ciclo.id, coletado_em=data, origem="COLETA_NATIVA", response_count=0,
                     displayable=False, qti_config_version="1.0.0", **extra)


def test_resposta_nao_tem_nenhuma_coluna_de_identidade(db):
    """A ausência é o mecanismo: sem coluna de identidade, não há como
    reconstruir quem respondeu o quê. Mesmo princípio do §48."""
    cols = {c.name for c in inspect(RespostaQTI).columns}
    proibidas = {"aluno_id", "estudante_id", "student_id", "nome", "email",
                 "matricula", "ip", "ip_address", "user_agent", "device_id", "session_id"}
    assert cols & proibidas == set(), f"coluna de identidade em RespostaQTI: {cols & proibidas}"
    assert "response_index" in cols


def test_coleta_declara_a_origem(db, ciclo):
    c = ColetaQTI(ciclo_id=ciclo.id, coletado_em=dt.date(2026, 3, 1),
                  origem="IMPORTACAO_EXTERNA", response_count=12, displayable=True,
                  qti_config_version="1.0.0")
    db.add(c); db.commit(); db.refresh(c)
    assert c.origem == "IMPORTACAO_EXTERNA"


def test_resultado_qti_recusa_duas_linhas_para_a_mesma_coleta(db, coleta_nativa):
    """Uma coleta tem UM resultado agregado — invariante de domínio (migração
    0010), não só cuidado de concorrência. Sem a restrição de unicidade em
    `coleta_id`, duas respostas chegando por links diferentes da mesma
    coleta (o limite de `app/publico/routes.py` é travado por link, não por
    coleta) poderiam fazer busca-ou-cria em paralelo no `ResultadoQTI`, as
    duas encontrarem vazio, as duas inserirem — e um relatório que
    encontrasse dois resultados agregados da mesma coleta escolheria
    arbitrariamente qual mostrar. Mesmo padrão de
    `test_consentimento_qti_recusa_duas_linhas_para_a_mesma_coleta`."""
    db.add(ResultadoQTI(coleta_id=coleta_nativa.id, octantes={"oc1": 0.5}, agency=0.0, communion=0.0))
    db.commit()
    db.add(ResultadoQTI(coleta_id=coleta_nativa.id, octantes={"oc1": 0.6}, agency=0.1, communion=0.1))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_o_banco_recusa_duas_coletas_vivas_na_mesma_data(db, ciclo):
    db.add(_coleta(ciclo, dt.date(2026, 9, 1)))
    db.add(_coleta(ciclo, dt.date(2026, 9, 1)))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_uma_coleta_apagada_nao_impede_outra_na_mesma_data(db, ciclo):
    """O índice é parcial — é o que mantém a reimportação funcionando."""
    db.add(_coleta(ciclo, dt.date(2026, 9, 1), deleted_at=dt.datetime.now(dt.timezone.utc)))
    db.add(_coleta(ciclo, dt.date(2026, 9, 1)))
    db.commit()


def test_dois_pedidos_simultaneos_de_link_reusam_a_mesma_coleta(db, ciclo):
    """Dois cliques em "gerar link": os dois procuram a coleta do dia, não acham, e os
    dois tentam criá-la. Aqui a corrida é reproduzida sem thread: logo antes do INSERT
    desta sessão, outra sessão cria e comita a mesma coleta. O índice recusa a segunda;
    coleta_nativa_do_dia tem de reler e devolver a que ganhou, sem erro 500."""
    disparou = []

    def outra_sessao_chega_antes(sessao, contexto, instancias):
        # Só no flush que vai inserir a coleta — nunca num flush anterior qualquer.
        if disparou or not any(isinstance(o, ColetaQTI) for o in sessao.new):
            return
        disparou.append(True)
        with SessionLocal(bind=get_engine()) as outra:
            outra.add(_coleta(ciclo, dt.date(2026, 9, 1)))
            outra.commit()

    event.listen(db, "before_flush", outra_sessao_chega_antes)
    try:
        coleta = coleta_nativa_do_dia(db, ciclo, dt.date(2026, 9, 1))
    finally:
        event.remove(db, "before_flush", outra_sessao_chega_antes)
    assert disparou, "a corrida não foi montada: o flush da coleta não aconteceu"
    db.commit()
    vivas = db.query(ColetaQTI).filter(ColetaQTI.deleted_at.is_(None)).all()
    assert len(vivas) == 1
    assert coleta.id == vivas[0].id


def test_concorrente_apagada_entre_o_erro_e_a_releitura_vira_409_nao_500(db, ciclo, monkeypatch):
    """Recorte mais fino da mesma corrida. O IntegrityError do INSERT perdedor só prova
    que havia uma coleta concorrente viva NAQUELE instante — nada garante que ela
    continue viva até a releitura, uma linha depois: outra requisição pode apagá-la
    logicamente (e comitar) nesse intervalo curtíssimo. _reusar_ou_recusar não pode
    presumir que a releitura sempre encontra alguém: sem essa checagem, `existente` vem
    None, `existente.origem` explode em AttributeError, e o professor que perdeu a
    corrida por uma fração de segundo ainda vê 500 — exatamente o que esta tarefa existe
    para eliminar.

    Monkeypatch em `_coleta_viva_da_data`, e não mais um `before_flush`: o ponto que
    importa aqui não é o INSERT que colide (já coberto pelo teste acima), é o instante
    ENTRE a exceção e a releitura, que nenhum evento de flush alcança — só interceptando
    a própria função de releitura dá para encaixar uma escrita ali. A 1ª chamada (antes
    do INSERT) passa direto; a 2ª (a releitura, após o IntegrityError) primeiro apaga a
    concorrente noutra sessão e comita, depois delega para a implementação real."""
    disparou = []

    def outra_sessao_chega_antes(sessao, contexto, instancias):
        if disparou or not any(isinstance(o, ColetaQTI) for o in sessao.new):
            return
        disparou.append(True)
        with SessionLocal(bind=get_engine()) as outra:
            outra.add(_coleta(ciclo, dt.date(2026, 9, 1)))
            outra.commit()

    original = qti_service._coleta_viva_da_data
    chamadas = []

    def releitura_acha_a_concorrente_ja_apagada(db_, ciclo_, data_):
        chamadas.append(True)
        if len(chamadas) == 2:
            with SessionLocal(bind=get_engine()) as terceira:
                concorrente = terceira.query(ColetaQTI).filter(
                    ColetaQTI.ciclo_id == ciclo_.id, ColetaQTI.coletado_em == data_,
                    ColetaQTI.deleted_at.is_(None)).one()
                concorrente.deleted_at = dt.datetime.now(dt.timezone.utc)
                terceira.commit()
        return original(db_, ciclo_, data_)

    monkeypatch.setattr(qti_service, "_coleta_viva_da_data", releitura_acha_a_concorrente_ja_apagada)
    event.listen(db, "before_flush", outra_sessao_chega_antes)
    try:
        with pytest.raises(AppError) as exc_info:
            coleta_nativa_do_dia(db, ciclo, dt.date(2026, 9, 1))
    finally:
        event.remove(db, "before_flush", outra_sessao_chega_antes)
    assert disparou, "a corrida não foi montada: o flush da coleta não aconteceu"
    assert len(chamadas) == 2, "a releitura não aconteceu: a mutação não foi exercida"
    assert exc_info.value.status == 409
    assert exc_info.value.code == "COLETA_CONCORRENTE"
    db.rollback()
