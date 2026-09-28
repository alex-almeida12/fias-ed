import datetime as dt
import threading
from datetime import date, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.db import SessionLocal, get_engine
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


def test_criar_um_segundo_link_revoga_o_primeiro(db, coleta_nativa):
    primeiro, token1 = criar_link(db, coleta_nativa, n_estudantes=30, dias=7)
    segundo, token2 = criar_link(db, coleta_nativa, n_estudantes=30, dias=7)
    assert link_valido(db, token1) is None
    assert link_valido(db, token2).id == segundo.id


def test_criar_link_nao_revoga_o_de_outra_coleta(db, ciclo, coleta_nativa):
    outra = ColetaQTI(ciclo_id=ciclo.id, coletado_em=date(2026, 10, 1), origem="COLETA_NATIVA",
                      response_count=0, displayable=False, qti_config_version="1.0.0")
    db.add(outra)
    db.commit()
    _, token_da_outra = criar_link(db, outra, n_estudantes=30, dias=7)
    criar_link(db, coleta_nativa, n_estudantes=30, dias=7)
    assert link_valido(db, token_da_outra) is not None


def test_o_banco_recusa_dois_links_vivos_na_mesma_coleta(db, coleta_nativa):
    """A garantia não pode depender só de criar_link: a restrição é do banco."""
    agora = dt.datetime.now(dt.timezone.utc)
    for sufixo in ("a", "b"):
        db.add(LinkQTI(coleta_id=coleta_nativa.id, token_hash=sufixo * 64,
                       expira_em=agora + dt.timedelta(days=7), limite_respostas=33))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_um_link_revogado_nao_impede_outro_vivo(db, coleta_nativa):
    """O índice é parcial: revogado ou apagado não conta."""
    agora = dt.datetime.now(dt.timezone.utc)
    db.add(LinkQTI(coleta_id=coleta_nativa.id, token_hash="a" * 64, revogado_em=agora,
                   expira_em=agora + dt.timedelta(days=7), limite_respostas=33))
    db.add(LinkQTI(coleta_id=coleta_nativa.id, token_hash="b" * 64,
                   expira_em=agora + dt.timedelta(days=7), limite_respostas=33))
    db.commit()


def test_criar_link_espera_quem_esta_criando_outro_para_a_mesma_coleta(db, coleta_nativa):
    """Dois cliques em "gerar link" disputam a coleta. Quem chega depois tem de esperar o
    primeiro terminar — senão não enxerga o link que ele criou, não o revoga, e o banco
    recusa o segundo link vivo com erro 500.

    A outra sessão trava a coleta com FOR SHARE, de propósito (rodada de conserto 1: FOR
    NO KEY UPDATE deixava passar uma mutação real — ver abaixo). FOR SHARE conflita com o
    FOR UPDATE de `criar_link` (então a trava de verdade ainda derruba este teste se
    sumir) e não conflita com o FOR KEY SHARE que a chave estrangeira do INSERT em
    link_qti pede (então, sem a trava de `criar_link`, ele ainda passaria direto e este
    teste ainda cairia) — as duas premissas do teste original se mantêm.

    O que FOR SHARE prova a mais: dois cliques REAIS são duas chamadas de `criar_link`,
    então o que importa é se a trava de `criar_link` conflita CONSIGO MESMA, não só
    contra um FOR NO KEY UPDATE externo. `with_for_update(read=True)` (FOR SHARE) não
    conflita com outro FOR SHARE — dois cliques concorrentes não se enfileirariam, os
    dois passariam pela revogação ao mesmo tempo, e o segundo a comitar esbarraria no
    índice único com IntegrityError (500), o mesmo defeito que a migração 0011 fecha.
    Uma trava externa em FOR NO KEY UPDATE não pega essa mutação (FOR NO KEY UPDATE
    conflita com FOR SHARE, então o teste continuaria verde por acidente); FOR SHARE
    pega, porque replica o lado fraco do par (o próprio `criar_link` concorrente)."""
    segurando = SessionLocal(bind=get_engine())
    segurando.execute(text("SELECT 1 FROM coleta_qti WHERE id = :id FOR SHARE"),
                      {"id": coleta_nativa.id})
    resultado = {}

    def gerar():
        with SessionLocal(bind=get_engine()) as s:
            coleta = s.get(ColetaQTI, coleta_nativa.id)
            resultado["link"], _ = criar_link(s, coleta, n_estudantes=30, dias=7)

    t = threading.Thread(target=gerar)
    t.start()
    t.join(timeout=1.0)
    try:
        assert t.is_alive(), "criar_link não esperou a trava da coleta"
    finally:
        segurando.commit()
        segurando.close()
        t.join(timeout=10)
    assert "link" in resultado
