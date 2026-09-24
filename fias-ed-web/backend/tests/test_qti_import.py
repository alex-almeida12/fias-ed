"""Importação do relatório do avalie-seu-professor (Task 5).

Os dois testes de versão declarada do plano original saíram desta suíte: fui
conferir no avalie-seu-professor e ele não declara versão nenhuma no arquivo
que exporta hoje (nem cabeçalho de comentário, nem coluna dedicada). Inventar
um formato de versão que o outro sistema não produz faria a importação
recusar todos os arquivos reais. A decisão e o porquê estão documentados em
app/qti/service.py, no ponto onde a checagem de versão deixou de existir.
"""
import datetime as dt

from app.models import AcessoAdmin, Ciclo, ColetaQTI, Disciplina, Escola, RespostaQTI, Turma
from tests.helpers import login, make_user

CABECALHO = "response_id," + ",".join(f"q{i}" for i in range(1, 25))


def _csv(n_linhas, valor=4):
    linhas = [CABECALHO]
    for i in range(n_linhas):
        linhas.append(f"r{i}," + ",".join([str(valor)] * 24))
    return "\n".join(linhas) + "\n"


def test_importa_e_persiste_as_respostas_item_a_item(db, client, ciclo):
    login(client, "professora-ciclo")
    r = client.post(f"/api/ciclos/{ciclo.id}/qti/importar",
                    files={"arquivo": ("export.csv", _csv(12), "text/csv")},
                    data={"coletado_em": "2026-03-01"})
    assert r.status_code == 201
    coleta = db.query(ColetaQTI).one()
    assert coleta.response_count == 12 and coleta.displayable is True
    assert coleta.origem == "IMPORTACAO_EXTERNA"
    assert db.query(RespostaQTI).filter_by(coleta_id=coleta.id).count() == 12


def test_arquivo_sem_nenhuma_resposta_e_recusado(db, client, ciclo):
    """Review Focus 3: exportação de turma que não respondeu."""
    login(client, "professora-ciclo")
    r = client.post(f"/api/ciclos/{ciclo.id}/qti/importar",
                    files={"arquivo": ("export.csv", CABECALHO + "\n", "text/csv")},
                    data={"coletado_em": "2026-03-01"})
    assert r.status_code == 422
    assert "nenhuma resposta" in r.json()["message"].lower()
    assert db.query(ColetaQTI).count() == 0


def test_valor_adulterado_recusa_o_arquivo_inteiro(db, client, ciclo):
    login(client, "professora-ciclo")
    linhas = _csv(12).splitlines()
    linhas[3] = linhas[3].replace(",4,", ",9,", 1)   # fora da escala 1..5
    r = client.post(f"/api/ciclos/{ciclo.id}/qti/importar",
                    files={"arquivo": ("export.csv", "\n".join(linhas), "text/csv")},
                    data={"coletado_em": "2026-03-01"})
    assert r.status_code == 422 and "linha 4" in r.json()["message"].lower()
    assert db.query(ColetaQTI).count() == 0


def test_reimportar_na_mesma_data_substitui_em_vez_de_duplicar(db, client, ciclo):
    """Review Focus 1: o professor clica duas vezes."""
    login(client, "professora-ciclo")
    for _ in range(2):
        client.post(f"/api/ciclos/{ciclo.id}/qti/importar",
                    files={"arquivo": ("export.csv", _csv(12), "text/csv")},
                    data={"coletado_em": "2026-03-01"})
    vivas = db.query(ColetaQTI).filter(ColetaQTI.deleted_at.is_(None)).all()
    assert len(vivas) == 1
    assert db.query(RespostaQTI).filter_by(coleta_id=vivas[0].id).count() == 12


def test_menos_de_dez_respostas_nao_e_erro_mas_nao_e_exibivel(db, client, ciclo):
    login(client, "professora-ciclo")
    r = client.post(f"/api/ciclos/{ciclo.id}/qti/importar",
                    files={"arquivo": ("export.csv", _csv(4), "text/csv")},
                    data={"coletado_em": "2026-03-01"})
    assert r.status_code == 201
    assert db.query(ColetaQTI).one().displayable is False


def test_importar_qti_com_ciclo_de_outro_professor_devolve_404(db, client, ciclo):
    """O brief mostrava `current_professor`/`actor.professor_id`, que não existem no
    projeto. O padrão real (app/ciclos/routes.py) é `current_actor` +
    `effective_professor_id`, com validação de posse do ciclo — sem ela, um professor
    autenticado poderia importar um relatório para o ciclo de outro."""
    outro = make_user(db, "outro-professor-qti")
    escola = Escola(name="Outra Escola", name_key="outra escola qti")
    db.add(escola)
    db.flush()
    turma = Turma(escola_id=escola.id, professor_id=outro.id, name="7º Ano A")
    disciplina = Disciplina(professor_id=outro.id, name="História")
    db.add_all([turma, disciplina])
    db.flush()
    ciclo_do_outro = Ciclo(turma_id=turma.id, disciplina_id=disciplina.id, professor_id=outro.id,
                          n_aulas_previstas=8, iniciado_em=dt.date(2026, 3, 1))
    db.add(ciclo_do_outro)
    db.commit()

    login(client, "professora-ciclo")
    r = client.post(f"/api/ciclos/{ciclo_do_outro.id}/qti/importar",
                    files={"arquivo": ("export.csv", _csv(12), "text/csv")},
                    data={"coletado_em": "2026-03-01"})
    assert r.status_code == 404
    assert db.query(ColetaQTI).count() == 0


def test_importacao_via_agir_como_e_auditada(client_factory, db, ciclo, professor):
    """Conserto 1: é o dado mais sensível da fatia (percepção dos estudantes sobre o
    professor); sem audit(), seria a única escrita do sistema sem rastro de quem a fez.
    O recurso auditado é a coleta (não o ciclo): resource_id só existe depois que a
    coleta é criada, e "ciclo"/"create" já é usado para a criação do ciclo em si."""
    make_user(db, "admin-qti", role="ADMIN_LOCAL")
    admin = client_factory()
    login(admin, "admin-qti")
    admin.post("/api/admin/agir-como", json={"professor_id": str(professor.id)})

    r = admin.post(f"/api/ciclos/{ciclo.id}/qti/importar",
                   files={"arquivo": ("export.csv", _csv(12), "text/csv")},
                   data={"coletado_em": "2026-03-01"})
    assert r.status_code == 201
    coleta_id = r.json()["id"]
    row = db.query(AcessoAdmin).filter_by(resource="coleta_qti", action="create").one()
    assert str(row.resource_id) == coleta_id


def test_importacao_na_propria_conta_nao_e_auditada(db, client, ciclo):
    """Prova que o conserto usa audit() (que é no-op fora de 'agir como'), não um
    record() direto que gravaria também para o professor operando na própria conta."""
    login(client, "professora-ciclo")
    r = client.post(f"/api/ciclos/{ciclo.id}/qti/importar",
                    files={"arquivo": ("export.csv", _csv(12), "text/csv")},
                    data={"coletado_em": "2026-03-01"})
    assert r.status_code == 201
    assert db.query(AcessoAdmin).count() == 0


def test_arquivo_fora_de_utf8_devolve_422(db, client, ciclo):
    login(client, "professora-ciclo")
    conteudo = "seção".encode("cp1252")
    r = client.post(f"/api/ciclos/{ciclo.id}/qti/importar",
                    files={"arquivo": ("export.csv", conteudo, "text/csv")},
                    data={"coletado_em": "2026-03-01"})
    assert r.status_code == 422
    assert r.json()["error_code"] == "QTI_ARQUIVO_ILEGIVEL"
    assert db.query(ColetaQTI).count() == 0
