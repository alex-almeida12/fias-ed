import datetime as dt

from app.models import Ciclo


def test_ciclo_nasce_aberto_e_com_o_numero_declarado(db, turma, disciplina, professor):
    c = Ciclo(turma_id=turma.id, disciplina_id=disciplina.id, professor_id=professor.id,
              n_aulas_previstas=8, iniciado_em=dt.date(2026, 3, 1))
    db.add(c); db.commit(); db.refresh(c)
    assert c.encerrado_em is None
    assert c.n_aulas_previstas == 8
    assert c.deleted_at is None
