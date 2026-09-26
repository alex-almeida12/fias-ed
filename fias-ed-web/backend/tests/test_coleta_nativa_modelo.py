"""§7 da spec: nenhuma identidade de respondente é persistida, e o
consentimento não se liga à resposta. Estes testes travam isso na forma das
tabelas, como test_diarize_nao_grava_o_rotulo_da_voz_em_lugar_nenhum faz para
a voz — não basta ninguém gravar identidade hoje; a coluna não pode existir."""
from app.models import ConsentimentoQTI, LinkQTI, RespostaQTI


def test_nenhuma_tabela_da_coleta_nativa_tem_coluna_de_identidade():
    proibidas = {"ip", "ip_address", "endereco_ip", "user_agent", "device_id",
                 "aluno_id", "estudante_id", "email", "nome", "matricula", "session_id"}
    for modelo in (LinkQTI, ConsentimentoQTI, RespostaQTI):
        colunas = {c.name for c in modelo.__table__.columns}
        assert not (colunas & proibidas), f"{modelo.__tablename__}: {colunas & proibidas}"


def test_consentimento_nao_tem_caminho_para_a_resposta():
    """Registra-se QUE houve consentimento, não DE QUEM é qual resposta. Uma
    chave estrangeira para RespostaQTI — ou uma coluna que guarde o índice do
    respondente — reconstruiria o vínculo que o §7 proíbe."""
    colunas = {c.name for c in ConsentimentoQTI.__table__.columns}
    assert "resposta_id" not in colunas and "response_index" not in colunas
    alvos = {fk.column.table.name for c in ConsentimentoQTI.__table__.columns for fk in c.foreign_keys}
    assert "resposta_qti" not in alvos


def test_link_guarda_o_hash_do_token_nunca_o_token():
    colunas = {c.name for c in LinkQTI.__table__.columns}
    assert "token_hash" in colunas
    assert "token" not in colunas
