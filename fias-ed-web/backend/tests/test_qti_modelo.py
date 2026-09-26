import datetime as dt

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app.models import ColetaQTI, ResultadoQTI, RespostaQTI


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
