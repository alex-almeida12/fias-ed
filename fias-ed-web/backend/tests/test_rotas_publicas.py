"""As três rotas sem autenticação do sistema. O que se testa aqui não é só o
caminho feliz: é que o limite não é furado, que resposta incompleta não entra,
e que nada sobre o professor ou a turma vaza para quem abre o link."""
import datetime as dt
from datetime import timezone

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import OperationalError

from app.core.config import get_settings
from app.core.db import SessionLocal, get_engine
from app.models import ConsentimentoQTI, LinkQTI, RespostaQTI
from app.publico.routes import COOKIE_CONSENTIMENTO, _valor_consentimento
from app.qti.links import criar_link, revogar

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


def test_link_invalido_expirado_e_revogado_dao_a_mesma_resposta_nas_tres_rotas(db, client_publico, coleta_nativa):
    """A garantia central do link público (§10: "a diferença entre 'não
    existe' e 'expirou' já é informação sobre a turma") só tinha cobertura
    de HTTP para token inventado — nada no nível da rota travava uma
    regressão que voltasse a distinguir expirado de revogado; a garantia se
    sustentava só porque `link_valido` já reduz os três casos a um `None`
    só. Aqui as três rotas são batidas com um token inexistente, um expirado
    de verdade e um revogado de verdade, e os corpos são comparados ENTRE SI
    — não contra texto copiado à mão — para o teste continuar valendo se a
    mensagem de erro mudar."""
    token_inexistente = "token-que-nao-existe-de-jeito-nenhum"

    link_expirado, token_expirado = criar_link(db, coleta_nativa, n_estudantes=30, dias=7)
    link_expirado.expira_em = dt.datetime.now(timezone.utc) - dt.timedelta(seconds=1)
    db.commit()

    link_revogado, token_revogado = criar_link(db, coleta_nativa, n_estudantes=30, dias=7)
    revogar(db, link_revogado)

    rotas = (
        ("GET", "/publico/qti/{token}", None),
        ("POST", "/publico/qti/{token}/consentir", {"documento_versao": "1.0.0"}),
        ("POST", "/publico/qti/{token}/responder", {"respostas": RESPOSTAS}),
    )
    for metodo, modelo, corpo in rotas:
        base = client_publico.request(metodo, modelo.format(token=token_inexistente), json=corpo)
        expirado = client_publico.request(metodo, modelo.format(token=token_expirado), json=corpo)
        revogado = client_publico.request(metodo, modelo.format(token=token_revogado), json=corpo)

        assert base.status_code == 404, (metodo, modelo, base.status_code)
        assert expirado.status_code == 404 == revogado.status_code, (metodo, modelo)
        assert expirado.json() == base.json() == revogado.json(), (metodo, modelo)


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


def test_o_limite_e_respeitado_em_envios_sucessivos(db, client_publico, coleta_nativa):
    """Renomeado (era `test_o_limite_nao_e_furado_por_dois_envios_ao_mesmo_tempo`):
    o nome antigo prometia concorrência que este teste não prova. O
    `TestClient` é síncrono — cada `post()` completa inteiro (grava e comita)
    antes do próximo começar — então não há aqui duas requisições realmente
    simultâneas em nenhum momento; cada tentativa sempre vê o commit da
    anterior. O que isto prova de fato é mais estreito, mas ainda vale: que a
    contagem não escorrega ao longo de vários envios sucessivos, mesmo depois
    de o limite já ter sido atingido (não é só "a próxima falha", é "todas as
    seguintes continuam falhando").

    Quem prova que a trava serializa concorrência de verdade é
    `test_for_update_no_link_serializa_duas_sessoes`, logo abaixo — sem HTTP,
    com duas sessões de banco reais."""
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


def test_for_update_no_link_serializa_duas_sessoes(db, coleta_nativa):
    """Review Focus 2, provado na camada onde a garantia realmente vive.

    Nenhum teste que passe pelo `TestClient` cria concorrência de verdade —
    ele é síncrono, então duas chamadas HTTP nunca disputam a mesma linha ao
    mesmo tempo; a de cima sempre comita antes da de baixo começar. Por isso
    este teste não usa `client_publico` nem HTTP: abre duas sessões de banco
    reais (duas conexões de verdade) e verifica a primitiva que
    `app/publico/routes.py` usa (`SELECT ... FOR UPDATE` sobre `LinkQTI`) do
    jeito que ela tem que se comportar sob disputa — é a garantia que o
    endpoint depende dela ter, não um substituto para testar o endpoint.

    Sessão A trava a linha do link e segura a transação aberta (sem comitar).
    Sessão B, com um `lock_timeout` curto, tenta a mesma trava na mesma
    linha: se `FOR UPDATE` está de fato bloqueando, B tem que estourar o
    timeout e falhar — não silenciosamente ter sucesso. Depois A libera (comita)
    e a mesma tentativa de B, numa transação nova, tem que suceder sem espera
    nenhuma."""
    link, _ = criar_link(db, coleta_nativa, n_estudantes=30, dias=7)
    link_id = link.id

    # Sessão A: trava a linha e não comita — é o que held-a-lock significa.
    db.execute(select(LinkQTI).where(LinkQTI.id == link_id).with_for_update())

    # Sessão B: outra conexão de verdade com o banco, não um segundo uso da mesma.
    db_b = SessionLocal(bind=get_engine())
    try:
        db_b.execute(text("SET LOCAL lock_timeout = '500ms'"))
        with pytest.raises(OperationalError):
            db_b.execute(select(LinkQTI).where(LinkQTI.id == link_id).with_for_update())
        # A transação de B abortou com o erro do Postgres; precisa de rollback
        # antes de reusar a conexão para qualquer outro comando.
        db_b.rollback()

        # Sessão A libera a trava...
        db.commit()

        # ...e agora a mesma consulta em B, numa transação nova, não espera nada.
        travado = db_b.execute(select(LinkQTI).where(LinkQTI.id == link_id).with_for_update()).scalar_one()
        assert travado.id == link_id
        db_b.commit()
    finally:
        db_b.close()


def test_a_coleta_nao_e_exibivel_com_nove_respostas(db, client_publico, coleta_nativa):
    """Achado da revisão: com exatamente dez respostas (o limiar), um `Web`
    que decidisse `displayable` por conta própria (`coleta.displayable =
    True`, fixo) coincidiria com o valor certo, e o teste abaixo passaria do
    mesmo jeito — dando confiança falsa justo no ponto que a spec protege
    (com poucos respondentes numa turma grande, o professor pode inferir
    quem respondeu). Nove respostas é o caso que distingue: o motor
    (`aggregate`) diz que NÃO é exibível abaixo do limiar, e só um `Web` que
    de fato persista o que `aggregate` devolveu — em vez de inventar — pega
    isso."""
    token = _token(db, coleta_nativa, n=20)
    for _ in range(9):
        client_publico.post(f"/publico/qti/{token}/consentir", json={"documento_versao": "1.0.0"})
        client_publico.post(f"/publico/qti/{token}/responder", json={"respostas": RESPOSTAS})
    db.refresh(coleta_nativa)
    assert coleta_nativa.response_count == 9 and coleta_nativa.displayable is False


def test_a_coleta_passa_a_ser_exibivel_na_decima_resposta(db, client_publico, coleta_nativa):
    """`min_responses` é 10 em qti_config.json, e quem decide é o motor:
    `aggregate` devolve `displayable`. O Web só persiste o que ele disse.
    Complementa `test_a_coleta_nao_e_exibivel_com_nove_respostas`: aquele
    prova o lado "abaixo do limiar, não exibível"; este prova "no limiar,
    exibível" — juntos, os dois lados do limite."""
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


def test_cookie_forjado_com_o_link_id_cru_e_recusado(db, client_publico, coleta_nativa):
    """A razão desta tarefa (achado da verificação final, 2026-09-26): antes
    do HMAC, `_consentiu_na_sessao` comparava o `link.id` cru contra o
    cookie. O estudante não recebe o `link.id` em resposta nenhuma, mas quem
    o obtivesse por outro meio gravava resposta sem nunca passar por
    `/consentir` — e a coleta ficava com `aceites = 0` e uma resposta
    registrada. As duas afirmações importam: o 409 sozinho não prova que
    nada entrou."""
    link, token = criar_link(db, coleta_nativa, n_estudantes=30, dias=7)
    client_publico.cookies.set(COOKIE_CONSENTIMENTO, str(link.id))
    r = client_publico.post(f"/publico/qti/{token}/responder", json={"respostas": RESPOSTAS})
    assert r.status_code == 409
    assert db.query(RespostaQTI).count() == 0


def test_o_valor_de_consentimento_de_um_link_nao_vale_para_outro(db, client_publico, coleta_nativa):
    """O que impede o HMAC de virar uma senha universal: ele é uma função do
    par (link.id, link.token_hash), não só do id. Consentir no link A e
    tentar usar o valor resultante no link B tem que ser recusado do mesmo
    jeito que o cookie cru era."""
    link_a, token_a = criar_link(db, coleta_nativa, n_estudantes=30, dias=7)
    link_b, token_b = criar_link(db, coleta_nativa, n_estudantes=30, dias=7)

    client_publico.post(f"/publico/qti/{token_a}/consentir", json={"documento_versao": "1.0.0"})
    valor_de_a = _valor_consentimento(link_a)
    assert valor_de_a in client_publico.cookies.get(COOKIE_CONSENTIMENTO, "").split(",")

    client_publico.cookies.set(COOKIE_CONSENTIMENTO, valor_de_a)
    r = client_publico.post(f"/publico/qti/{token_b}/responder", json={"respostas": RESPOSTAS})
    assert r.status_code == 409
    assert db.query(RespostaQTI).count() == 0


def test_o_cookie_emitido_nao_contem_o_link_id(db, client_publico, coleta_nativa):
    """O ganho de graça do HMAC: o cookie deixa de carregar o `link.id` em
    formato nenhum. Compara contra o id de verdade (não contra um literal
    escrito à mão), para o teste continuar valendo se o formato do id mudar."""
    token = _token(db, coleta_nativa)
    r = client_publico.post(f"/publico/qti/{token}/consentir", json={"documento_versao": "1.0.0"})
    link = db.query(LinkQTI).one()
    cookie_emitido = r.cookies.get(COOKIE_CONSENTIMENTO)
    assert cookie_emitido is not None
    assert str(link.id) not in cookie_emitido.split(",")


def test_o_hmac_depende_do_token_hash_e_nao_so_do_id():
    """Fora do brief original desta tarefa: a verificação de mutação pedida
    para o teste 3 ("troque `link.token_hash` por uma chave fixa") não o
    derruba, porque a mensagem do HMAC já é `link.id` — dois `id`s diferentes
    já produzem valores diferentes com QUALQUER chave, fixa ou não. O teste 3
    prova então uma propriedade mais fraca do que a decisão do pesquisador
    precisa: que o `id` participa do cálculo, não que o `token_hash`
    participa. Este teste unitário fecha essa lacuna diretamente: dois
    objetos com o MESMO `id` e `token_hash` diferentes (não dá para
    persistir dois `LinkQTI` com o mesmo id de verdade — é chave primária —
    então o duplo local é a forma de isolar só essa variável) têm que
    produzir valores diferentes. Sob a mutação "chave fixa", ele falha; sob o
    código real, passa."""
    from types import SimpleNamespace
    link_1 = SimpleNamespace(id="11111111-1111-1111-1111-111111111111", token_hash="hash-a")
    link_2 = SimpleNamespace(id="11111111-1111-1111-1111-111111111111", token_hash="hash-b")
    assert _valor_consentimento(link_1) != _valor_consentimento(link_2)


def test_um_navegador_com_dois_links_consentidos_responde_aos_dois(db, client_publico, coleta_nativa):
    """A lista de valores no cookie não pode ter virado campo único: um
    estudante que responde a dois questionários no mesmo navegador precisa
    continuar conseguindo consentir e responder aos dois."""
    token_a = _token(db, coleta_nativa)
    token_b = _token(db, coleta_nativa)

    client_publico.post(f"/publico/qti/{token_a}/consentir", json={"documento_versao": "1.0.0"})
    client_publico.post(f"/publico/qti/{token_b}/consentir", json={"documento_versao": "1.0.0"})

    assert client_publico.post(f"/publico/qti/{token_a}/responder",
                               json={"respostas": RESPOSTAS}).status_code == 201
    assert client_publico.post(f"/publico/qti/{token_b}/responder",
                               json={"respostas": RESPOSTAS}).status_code == 201
    assert db.query(RespostaQTI).count() == 2


def _atributos_do_cookie(set_cookie: str) -> list[str]:
    return [parte.strip().lower() for parte in set_cookie.split(";")]


def test_em_http_o_cookie_de_consentimento_nao_e_secure(db, client_publico, coleta_nativa, monkeypatch):
    """Na sala, sem TLS, a URL pública é http://IP:8081. Os navegadores descartam cookie
    Secure vindo de http fora de localhost, e o estudante receberia 409 em todo envio."""
    monkeypatch.setenv("PUBLIC_URL", "http://192.168.137.1:8081")
    get_settings.cache_clear()
    _, token = criar_link(db, coleta_nativa, n_estudantes=30, dias=7)
    r = client_publico.post(f"/publico/qti/{token}/consentir", json={"documento_versao": "1.0.0"})
    assert r.status_code == 201
    atributos = _atributos_do_cookie(r.headers["set-cookie"])
    assert atributos[0].startswith("fias_qti_consentimento=")
    assert "secure" not in atributos
    assert "httponly" in atributos
    assert "samesite=strict" in atributos
    assert "path=/publico" in atributos


def test_em_https_o_cookie_de_consentimento_e_secure(db, client_publico, coleta_nativa, monkeypatch):
    monkeypatch.setenv("PUBLIC_URL", "https://fias.exemplo")
    get_settings.cache_clear()
    _, token = criar_link(db, coleta_nativa, n_estudantes=30, dias=7)
    r = client_publico.post(f"/publico/qti/{token}/consentir", json={"documento_versao": "1.0.0"})
    assert "secure" in _atributos_do_cookie(r.headers["set-cookie"])
