"""Task 13: GET /api/aulas/{id}/padroes — a tela de padrões de interação.

`aula_classificada` reaproveita o mesmo desenho de test_job_fias.py: chama
`fias_service.classificar_aula` direto (não passa pela fila), com um
classificador falso fixado em categoria 5 (docente, sem forçar 8/9) — para o
segmento do ALUNO, `constrain_by_role` restringe para 8 ou 9 de qualquer jeito
(spec §4.2), então o cenário fica: um segmento do professor em categoria 5
("Expõe", influência direta) e um do aluno em categoria 8 ("Resposta do
aluno"). Isso basta para exercitar faixa, matriz E observações com evidência
real, sem reimplementar nenhuma regra científica aqui.

`cliente` segue o padrão de test_escolha_voz.py: um cliente autenticado como a
professora dona das aulas das fixtures abaixo.
"""
import uuid

import pytest
from sqlalchemy import select, update

from app.fias import service as fias_service
from app.ml.fakes import ClassificadorFalso
from app.models import (Audio, Falante, IndicadorFIAS, Professor, Segmento, Transcricao,
                        TrechoDeFala, utcnow)
from tests.helpers import login, make_aula, make_user


@pytest.fixture
def cliente(client_factory, db):
    make_user(db, "diana-padroes")
    c = client_factory()
    login(c, "diana-padroes")
    return c


@pytest.fixture
def classificador_falso(monkeypatch):
    clf = ClassificadorFalso(categoria_fixa=5)
    monkeypatch.setattr(fias_service, "obter_classificador", lambda: clf)
    return clf


def _construir_aula(db, *, status: str, segmentos_spec: list[tuple[str, str]],
                    passo_ms: int = 3_000, duracao_ms: int | None = None,
                    fala: list[tuple[int, int, int]] | None = None):
    """`passo_ms`/`duracao_ms`/`fala` existem para os testes que precisam de
    uma linha do tempo que não seja um segmento por intervalo de 3 s — que é
    justamente o pressuposto que esta fatia derrubou."""
    prof = db.scalar(select(Professor).where(Professor.username == "diana-padroes"))
    aula = make_aula(db, prof, status=status)
    audio = Audio(aula_id=aula.id, original_filename="aula.wav", internal_filename=f"{uuid.uuid4()}.wav",
                 path="original/aula.wav", mime_type="audio/wav", size_bytes=1,
                 duration_ms=duracao_ms if duracao_ms is not None else len(segmentos_spec) * passo_ms,
                 sha256="0" * 64, channels=1, sample_rate=16000,
                 is_original=True, derived_from_audio_id=None)
    db.add(audio)
    db.flush()
    transcricao = Transcricao(aula_id=aula.id, audio_id=audio.id, asr_model_id="fake-asr")
    db.add(transcricao)
    db.flush()
    falantes = {
        "PROFESSOR": Falante(transcricao_id=transcricao.id, diarization_label="SPEAKER_00", role="PROFESSOR"),
        "ALUNO": Falante(transcricao_id=transcricao.id, diarization_label="merged", role="ALUNO"),
    }
    db.add_all(falantes.values())
    db.flush()
    for i, (papel, texto) in enumerate(segmentos_spec):
        db.add(Segmento(transcricao_id=transcricao.id, falante_id=falantes[papel].id, start_ms=i * passo_ms,
                        end_ms=(i + 1) * passo_ms, texto_original_asr=texto, texto_revisado=texto, revisado=True))
    for inicio, fim, n_vozes in fala or []:
        db.add(TrechoDeFala(transcricao_id=transcricao.id, inicio_ms=inicio, fim_ms=fim, n_vozes=n_vozes))
    db.commit()
    return aula


@pytest.fixture
def aula_classificada(db, cliente, classificador_falso):
    aula = _construir_aula(db, status="READY_FOR_FIAS", segmentos_spec=[
        ("PROFESSOR", "vamos começar a explicar a questão"),
        ("ALUNO", "o que vocês acham disso"),
    ])
    fias_service.classificar_aula(db, aula)
    aula.status, aula.error_code = "FIAS_COMPLETED", None
    db.commit()
    return aula


@pytest.fixture
def aula_em_revisao(db, cliente):
    return _construir_aula(db, status="READY_FOR_TRANSCRIPT_REVIEW",
                           segmentos_spec=[("PROFESSOR", "vamos começar a explicar a questão")])


def test_padroes_traz_faixa_matriz_e_indices(cliente, aula_classificada):
    r = cliente.get(f"/api/aulas/{aula_classificada.id}/padroes")
    assert r.status_code == 200
    corpo = r.json()
    assert len(corpo["matriz"]) == 10 and all(len(l) == 10 for l in corpo["matriz"])
    assert corpo["indices"]
    assert corpo["faixa"]


def test_cada_observacao_vem_com_evidencia(cliente, aula_classificada):
    corpo = cliente.get(f"/api/aulas/{aula_classificada.id}/padroes").json()
    assert corpo["observacoes"]
    assert all(o["evidencias"] for o in corpo["observacoes"])
    # A evidência é um trecho real da transcrição, não um resumo inventado.
    trechos = {ev["trecho"] for o in corpo["observacoes"] for ev in o["evidencias"]}
    assert "o que vocês acham disso" in trechos


def test_nenhum_indice_vem_com_limiar_de_bom_ou_ruim(cliente, aula_classificada):
    """spec §8.4: os limiares estão PENDING_SCIENTIFIC_VALIDATION; mostrar um
    número contra meta não validada inventa um veredito."""
    corpo = cliente.get(f"/api/aulas/{aula_classificada.id}/padroes").json()
    assert corpo["indices"]
    for i in corpo["indices"]:
        assert set(i) == {"codigo", "nome", "valor", "descricao"}
        texto = (i["descricao"] + i["nome"]).lower()
        assert not any(p in texto for p in ("bom", "ruim", "ideal", "abaixo do esperado"))
        assert not any(p in texto for p in ("avaliaç", "avaliar", "nota", "desempenho", "ranking"))


def test_aula_ainda_nao_classificada_da_409(cliente, aula_em_revisao):
    r = cliente.get(f"/api/aulas/{aula_em_revisao.id}/padroes")
    assert r.status_code == 409


# ---- Desconfiança do brief: a armadilha registrada no progress.md para esta
# task é que IndicadorFIAS ganhou `deleted_at` numa task anterior sem nenhum
# ponto de leitura ainda. O caminho de produção de hoje só soft-deleta um
# indicador junto com a aula inteira (soft_delete_aula), e get_owned_aula já
# devolveria 404 antes de chegar aqui — então este teste soft-deleta o
# indicador isoladamente (bypass do fluxo normal) para travar a consulta em
# si, não o fluxo de exclusão. Sem o filtro `deleted_at.is_(None)` na consulta
# de IndicadorFIAS, este teste falha.
def test_indicador_excluido_nao_reaparece_na_tela(cliente, db, aula_classificada):
    db.execute(update(IndicadorFIAS).where(IndicadorFIAS.aula_id == aula_classificada.id)
              .values(deleted_at=utcnow()))
    db.commit()
    corpo = cliente.get(f"/api/aulas/{aula_classificada.id}/padroes").json()
    assert corpo["indices"] == []


# ---- a faixa de tempo não pode pintar além do fim da aula ---------------------


@pytest.fixture
def aula_com_muitas_marcas(db, cliente, classificador_falso):
    """Oito segmentos de 1,5 s alternando professor e aluno numa aula de 12 s.

    A codificação fiel ao protocolo registra TODA mudança de categoria: são oito
    marcas onde a regra de balde daria quatro. É exatamente o caso em que a
    faixa calculada por `índice × 3 s` sai do fim da aula."""
    aula = _construir_aula(db, status="READY_FOR_FIAS", passo_ms=1_500, duracao_ms=12_000,
                           segmentos_spec=[("PROFESSOR" if i % 2 == 0 else "ALUNO",
                                            "vamos explicar" if i % 2 == 0 else "o que vocês acham")
                                           for i in range(8)],
                           fala=[(0, 12_000, 1)])
    fias_service.classificar_aula(db, aula)
    aula.status, aula.error_code = "FIAS_COMPLETED", None
    db.commit()
    return aula


def test_a_faixa_nunca_passa_da_duracao_da_aula(cliente, db, aula_com_muitas_marcas):
    """O conserto: a faixa toma os tempos de cada marca, e não de `i × 3 s`.
    Com a conta antiga, os quatro últimos trechos começavam em 12 s, 15 s, 18 s
    e 21 s numa aula de 12 s — depois do fim, e com fim antes do começo."""
    corpo = cliente.get(f"/api/aulas/{aula_com_muitas_marcas.id}/padroes").json()
    faixa = corpo["faixa"]
    assert len(faixa) == 8
    assert all(f["inicio_ms"] < f["fim_ms"] <= 12_000 for f in faixa), faixa
    assert max(f["fim_ms"] for f in faixa) == 12_000


def test_a_faixa_cobre_a_aula_inteira_sem_buraco_e_sem_sobreposicao(cliente, aula_com_muitas_marcas):
    faixa = cliente.get(f"/api/aulas/{aula_com_muitas_marcas.id}/padroes").json()["faixa"]
    assert faixa[0]["inicio_ms"] == 0
    assert all(a["fim_ms"] == b["inicio_ms"] for a, b in zip(faixa, faixa[1:]))


# ---- o silêncio vem do separador de vozes ------------------------------------


@pytest.fixture
def aula_com_silencio(db, cliente, classificador_falso):
    """Quatro segmentos de ASR encostados, cobrindo 12 s sem lacuna nenhuma
    entre eles — é o que o vad_filter do Whisper produz. O separador de vozes
    diz que só os 3 s do começo e os 3 s do fim tiveram fala."""
    aula = _construir_aula(db, status="READY_FOR_FIAS",
                           segmentos_spec=[("PROFESSOR", "vamos explicar a questão")] * 4,
                           fala=[(0, 3_000, 1), (9_000, 12_000, 1)])
    fias_service.classificar_aula(db, aula)
    aula.status, aula.error_code = "FIAS_COMPLETED", None
    db.commit()
    return aula


def test_silencio_sai_do_separador_de_vozes_e_nao_das_lacunas_do_asr(cliente, aula_com_silencio):
    """A armadilha: entre os segmentos do ASR não há lacuna nenhuma, então quem
    medir não-fala por lacuna de segmento acha zero de silêncio e passa."""
    corpo = cliente.get(f"/api/aulas/{aula_com_silencio.id}/padroes").json()
    assert corpo["tempo_de_silencio_ms"] == 6_000
    assert [f["grupo"] for f in corpo["faixa"]] == ["direta", "silêncio", "silêncio", "direta"]


def test_aula_sem_linha_do_tempo_de_fala_nao_inventa_silencio(cliente, db, classificador_falso):
    """Aula diarizada antes desta versão: não há trecho de fala gravado. "Não se sabe
    onde houve fala" não pode virar "não houve fala"."""
    aula = _construir_aula(db, status="READY_FOR_FIAS",
                           segmentos_spec=[("PROFESSOR", "vamos explicar a questão")] * 4)
    fias_service.classificar_aula(db, aula)
    aula.status, aula.error_code = "FIAS_COMPLETED", None
    db.commit()
    corpo = cliente.get(f"/api/aulas/{aula.id}/padroes").json()
    assert corpo["tempo_de_silencio_ms"] == 0
    assert all(f["grupo"] != "silêncio" for f in corpo["faixa"])
