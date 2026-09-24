import datetime as dt

from sqlalchemy import inspect

from app.models import ColetaQTI, RespostaQTI


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
