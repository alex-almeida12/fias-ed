import datetime as dt
from datetime import timezone

from app.models import ColetaQTI, LinkQTI
from app.qti.links import criar_link, link_valido, revogar


def test_o_token_em_claro_nao_fica_no_banco(db, coleta_nativa):
    link, token = criar_link(db, coleta_nativa, n_estudantes=30, dias=7)
    assert token and len(token) >= 32
    assert link.token_hash != token
    assert token not in str(link.__dict__.values())


def test_limite_e_o_numero_de_estudantes_mais_dez_por_cento(db, coleta_nativa):
    link, _ = criar_link(db, coleta_nativa, n_estudantes=30, dias=7)
    assert link.limite_respostas == 33


def test_limite_arredonda_para_cima(db, coleta_nativa):
    """Turma de 12: 13,2 vira 14, não 13. Arredondar para baixo custaria a vaga
    de um estudante real; para cima, abre uma vaga a mais num link que já é
    limitado e temporário."""
    link, _ = criar_link(db, coleta_nativa, n_estudantes=12, dias=7)
    assert link.limite_respostas == 14


def test_token_certo_encontra_o_link(db, coleta_nativa):
    _, token = criar_link(db, coleta_nativa, n_estudantes=30, dias=7)
    assert link_valido(db, token) is not None


def test_token_errado_nao_encontra_nada(db, coleta_nativa):
    criar_link(db, coleta_nativa, n_estudantes=30, dias=7)
    assert link_valido(db, "nao-e-um-token-valido-qualquer-coisa") is None


def test_link_expirado_nao_vale(db, coleta_nativa):
    link, token = criar_link(db, coleta_nativa, n_estudantes=30, dias=7)
    link.expira_em = dt.datetime.now(timezone.utc) - dt.timedelta(seconds=1)
    db.commit()
    assert link_valido(db, token) is None


def test_link_revogado_nao_vale(db, coleta_nativa):
    link, token = criar_link(db, coleta_nativa, n_estudantes=30, dias=7)
    revogar(db, link)
    assert link_valido(db, token) is None


def test_link_de_coleta_apagada_nao_vale(db, coleta_nativa):
    """Review Focus 4: o professor apaga a coleta e o link antigo continua de
    pé — as respostas entrariam órfãs, numa coleta que ninguém mais lê."""
    from app.models import utcnow
    _, token = criar_link(db, coleta_nativa, n_estudantes=30, dias=7)
    coleta_nativa.deleted_at = utcnow()
    db.commit()
    assert link_valido(db, token) is None


def test_o_token_nunca_aparece_em_repr_nem_em_str(db, coleta_nativa):
    """Review Focus 1: o segredo do link é a única credencial do sistema. Um
    `repr` que o inclua vaza em traceback, em log de exceção e em mensagem de
    erro, todos lugares que ninguém inspeciona esperando encontrar credencial."""
    link, token = criar_link(db, coleta_nativa, n_estudantes=30, dias=7)
    assert token not in repr(link) and token not in str(link)
