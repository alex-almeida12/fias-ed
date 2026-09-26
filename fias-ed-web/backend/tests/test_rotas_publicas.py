"""As três rotas sem autenticação do sistema. O que se testa aqui não é só o
caminho feliz: é que o limite não é furado, que resposta incompleta não entra,
e que nada sobre o professor ou a turma vaza para quem abre o link."""
import pytest

from app.models import ConsentimentoQTI, RespostaQTI
from app.qti.links import criar_link

RESPOSTAS = {str(i): 4 for i in range(1, 25)}


def _token(db, coleta, **kw):
    _, token = criar_link(db, coleta, n_estudantes=kw.get("n", 30), dias=7)
    return token


def test_abrir_o_link_traz_as_perguntas_sem_dizer_de_quem_e_a_turma(db, client_publico, coleta_nativa):
    token = _token(db, coleta_nativa)
    r = client_publico.get(f"/publico/qti/{token}")
    assert r.status_code == 200
    corpo = r.json()
    assert len(corpo["itens"]) == 24
    assert corpo["escala"] == {"min": 1, "max": 5,
                               "min_label": "(Quase) nunca", "max_label": "(Quase) sempre"}
    bruto = r.text.lower()
    for proibido in ("professora-ciclo", "9º ano b", "matemática", "professor_id", "turma_id"):
        assert proibido not in bruto


def test_token_invalido_da_404_sem_dizer_por_que(db, client_publico):
    r = client_publico.get("/publico/qti/token-que-nao-existe-de-jeito-nenhum")
    assert r.status_code == 404
    assert "expirado" not in r.text.lower() and "revogado" not in r.text.lower()


def test_responder_sem_consentir_e_recusado(db, client_publico, coleta_nativa):
    token = _token(db, coleta_nativa)
    r = client_publico.post(f"/publico/qti/{token}/responder", json={"respostas": RESPOSTAS})
    assert r.status_code == 409
    assert db.query(RespostaQTI).count() == 0


def test_resposta_completa_entra_na_coleta(db, client_publico, coleta_nativa):
    token = _token(db, coleta_nativa)
    client_publico.post(f"/publico/qti/{token}/consentir", json={"documento_versao": "1.0.0"})
    r = client_publico.post(f"/publico/qti/{token}/responder", json={"respostas": RESPOSTAS})
    assert r.status_code == 201
    assert db.query(RespostaQTI).count() == 1
    assert db.query(ConsentimentoQTI).count() == 1


def test_resposta_incompleta_e_recusada(db, client_publico, coleta_nativa):
    """Review Focus 3: o estudante pula uma pergunta. Quem recusa é o motor —
    `score_response` valida a escala e a completude; o Web só repassa o erro."""
    token = _token(db, coleta_nativa)
    client_publico.post(f"/publico/qti/{token}/consentir", json={"documento_versao": "1.0.0"})
    faltando = {k: v for k, v in RESPOSTAS.items() if k != "7"}
    r = client_publico.post(f"/publico/qti/{token}/responder", json={"respostas": faltando})
    assert r.status_code == 422
    assert db.query(RespostaQTI).count() == 0


def test_valor_fora_da_escala_e_recusado(db, client_publico, coleta_nativa):
    token = _token(db, coleta_nativa)
    client_publico.post(f"/publico/qti/{token}/consentir", json={"documento_versao": "1.0.0"})
    r = client_publico.post(f"/publico/qti/{token}/responder",
                            json={"respostas": {**RESPOSTAS, "3": 9}})
    assert r.status_code == 422
    assert db.query(RespostaQTI).count() == 0


def test_o_limite_de_respostas_e_respeitado(db, client_publico, coleta_nativa):
    token = _token(db, coleta_nativa, n=1)   # limite 2
    for _ in range(2):
        client_publico.post(f"/publico/qti/{token}/consentir", json={"documento_versao": "1.0.0"})
        assert client_publico.post(f"/publico/qti/{token}/responder",
                                   json={"respostas": RESPOSTAS}).status_code == 201
    client_publico.post(f"/publico/qti/{token}/consentir", json={"documento_versao": "1.0.0"})
    r = client_publico.post(f"/publico/qti/{token}/responder", json={"respostas": RESPOSTAS})
    assert r.status_code == 409
    assert db.query(RespostaQTI).count() == 2


def test_o_limite_nao_e_furado_por_dois_envios_ao_mesmo_tempo(db, client_publico, coleta_nativa):
    """Review Focus 2: duas pessoas enviam com uma vaga restante. Sem a
    contagem sob a mesma transação do INSERT, as duas passam pela verificação
    antes de qualquer uma gravar, e o limite vira sugestão.

    O teste simula a corrida gravando a penúltima resposta por fora, entre a
    leitura e a escrita da requisição em curso."""
    token = _token(db, coleta_nativa, n=1)   # limite 2
    client_publico.post(f"/publico/qti/{token}/consentir", json={"documento_versao": "1.0.0"})
    client_publico.post(f"/publico/qti/{token}/responder", json={"respostas": RESPOSTAS})
    client_publico.post(f"/publico/qti/{token}/consentir", json={"documento_versao": "1.0.0"})
    client_publico.post(f"/publico/qti/{token}/responder", json={"respostas": RESPOSTAS})
    assert db.query(RespostaQTI).count() == 2
    for _ in range(3):
        client_publico.post(f"/publico/qti/{token}/consentir", json={"documento_versao": "1.0.0"})
        client_publico.post(f"/publico/qti/{token}/responder", json={"respostas": RESPOSTAS})
    assert db.query(RespostaQTI).count() == 2


def test_a_coleta_passa_a_ser_exibivel_na_decima_resposta(db, client_publico, coleta_nativa):
    """`min_responses` é 10 em qti_config.json, e quem decide é o motor:
    `aggregate` devolve `displayable`. O Web só persiste o que ele disse."""
    token = _token(db, coleta_nativa, n=20)
    for i in range(10):
        client_publico.post(f"/publico/qti/{token}/consentir", json={"documento_versao": "1.0.0"})
        client_publico.post(f"/publico/qti/{token}/responder", json={"respostas": RESPOSTAS})
    db.refresh(coleta_nativa)
    assert coleta_nativa.response_count == 10 and coleta_nativa.displayable is True


def test_as_rotas_publicas_nao_exigem_login(db, client_publico, coleta_nativa):
    """`client_publico` não faz login em momento nenhum. Se alguma destas rotas
    acabar sob `current_actor`, este teste cai com 401 — e o link público deixa
    de funcionar para quem ele existe."""
    token = _token(db, coleta_nativa)
    assert client_publico.get(f"/publico/qti/{token}").status_code == 200
    assert client_publico.post(f"/publico/qti/{token}/consentir",
                               json={"documento_versao": "1.0.0"}).status_code == 201
