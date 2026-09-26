"""§7 da spec: nenhuma identidade de respondente é persistida, e o
consentimento não se liga à resposta. Estes testes travam isso na forma das
tabelas por LISTA DE COLUNAS PERMITIDAS, não por lista de nomes proibidos.
Uma lista de proibidos só pega o que alguém pensou em proibir — a fatia
anterior já pagou esse preço, quando um campo de veredito com nome inocente
escapou de uma lista assim. Uma lista de permitidos quebra para QUALQUER
coluna nova, com qualquer nome: quem acrescentar uma coluna por um motivo
legítimo tem que atualizar esta lista conscientemente, lendo este comentário
no processo."""
import pytest
from sqlalchemy.exc import IntegrityError

from app.models import ConsentimentoQTI, LinkQTI, RespostaQTI


def test_link_qti_so_tem_as_colunas_permitidas():
    permitidas = {"id", "created_at", "updated_at", "deleted_at", "version", "sync_status",
                  "coleta_id", "token_hash", "expira_em", "limite_respostas", "revogado_em"}
    colunas = {c.name for c in LinkQTI.__table__.columns}
    assert colunas == permitidas, colunas ^ permitidas


def test_consentimento_qti_so_tem_as_colunas_permitidas():
    """Uma linha por coleta, não por estudante: `aceites` é contador, não
    carimbo de tempo individual — ver o docstring de ConsentimentoQTI para o
    porquê (o carimbo por aceite era o canal de correlação temporal com
    RespostaQTI que o §7 proíbe)."""
    permitidas = {"id", "created_at", "updated_at", "deleted_at", "version", "sync_status",
                  "coleta_id", "documento_versao", "aceites"}
    colunas = {c.name for c in ConsentimentoQTI.__table__.columns}
    assert colunas == permitidas, colunas ^ permitidas


def test_resposta_qti_so_tem_as_colunas_permitidas():
    permitidas = {"id", "created_at", "updated_at", "deleted_at", "version", "sync_status",
                  "coleta_id", "response_index", "respostas"}
    colunas = {c.name for c in RespostaQTI.__table__.columns}
    assert colunas == permitidas, colunas ^ permitidas


def test_consentimento_nao_tem_caminho_para_a_resposta():
    """Registra-se QUE houve consentimento, não DE QUEM é qual resposta. Uma
    chave estrangeira para RespostaQTI — ou uma coluna que guarde o índice do
    respondente — reconstruiria o vínculo que o §7 proíbe. ConsentimentoQTI
    é uma linha por coleta, não por estudante: sem linha por estudante, não
    há o que parear com RespostaQTI, nem por chave nem por tempo."""
    colunas = {c.name for c in ConsentimentoQTI.__table__.columns}
    assert "resposta_id" not in colunas and "response_index" not in colunas
    alvos = {fk.column.table.name for c in ConsentimentoQTI.__table__.columns for fk in c.foreign_keys}
    assert "resposta_qti" not in alvos


def test_link_guarda_o_hash_do_token_nunca_o_token():
    colunas = {c.name for c in LinkQTI.__table__.columns}
    assert "token_hash" in colunas
    assert "token" not in colunas


def test_consentimento_qti_recusa_duas_linhas_para_a_mesma_coleta(db, ciclo, coleta_em):
    """'Uma linha por coleta' precisa ser garantia de banco, não de boa
    vontade de quem chamar: sem a restrição de unicidade em `coleta_id`, duas
    respostas chegando ao mesmo tempo poderiam fazer busca-ou-cria em
    paralelo, as duas encontrarem vazio, as duas inserirem — e a coleta
    voltaria a ter estrutura por evento, reabrindo o pareamento que a linha
    única existe para fechar (§7)."""
    coleta = coleta_em(ciclo, "2026-03-01")
    db.add(ConsentimentoQTI(coleta_id=coleta.id, documento_versao="1.0", aceites=1))
    db.commit()
    db.add(ConsentimentoQTI(coleta_id=coleta.id, documento_versao="1.0", aceites=1))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
