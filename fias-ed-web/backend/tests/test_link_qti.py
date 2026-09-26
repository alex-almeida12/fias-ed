import datetime as dt
from datetime import timezone

from app.models import Base, ColetaQTI, LinkQTI
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


def test_limite_nao_erra_por_arredondamento_de_ponto_flutuante(db, coleta_nativa):
    """Achado da revisão: `n * 1.10` em ponto flutuante dá
    55.00000000000001 para n=50, e `math.ceil` ingênuo entrega 56 em vez de
    55 — o mesmo acontece em 90 e 100. Os tamanhos 12 e 30, que os outros
    testes usam, escapam por coincidência de representação binária; só um
    teste com esses tamanhos prova o conserto."""
    link_50, _ = criar_link(db, coleta_nativa, n_estudantes=50, dias=7)
    assert link_50.limite_respostas == 55
    link_100, _ = criar_link(db, coleta_nativa, n_estudantes=100, dias=7)
    assert link_100.limite_respostas == 110


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


def test_link_qti_e_a_base_nao_definem_repr_nem_str_proprios():
    """Review Focus 1: o segredo do link é a única credencial do sistema. Um
    `repr` que o inclua vaza em traceback, em log de exceção e em mensagem de
    erro, todos lugares que ninguém inspeciona esperando encontrar credencial.

    A versão anterior deste teste comparava o token contra `repr(link)` e
    `str(link)` — mas passaria mesmo com o token em claro no banco, porque
    nem `LinkQTI` nem `Base` definem `__repr__`/`__str__` próprios, e a repr
    padrão do SQLAlchemy nunca imprime valores de campo (achado da revisão).
    Este teste vigia a AUSÊNCIA em si, não um comportamento que ela garante
    de graça: se algum dia alguém acrescentar um `__repr__`/`__str__` por
    conveniência, este teste acende, e a decisão sobre o que aquela
    representação pode imprimir passa a ser consciente."""
    for classe in (LinkQTI, Base):
        assert "__repr__" not in classe.__dict__
        assert "__str__" not in classe.__dict__
