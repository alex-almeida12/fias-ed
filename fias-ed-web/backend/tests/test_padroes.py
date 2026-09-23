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
from app.models import Audio, Falante, IndicadorFIAS, Professor, Segmento, Transcricao, utcnow
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


def _construir_aula(db, *, status: str, segmentos_spec: list[tuple[str, str]]):
    prof = db.scalar(select(Professor).where(Professor.username == "diana-padroes"))
    aula = make_aula(db, prof, status=status)
    audio = Audio(aula_id=aula.id, original_filename="aula.wav", internal_filename=f"{uuid.uuid4()}.wav",
                 path="original/aula.wav", mime_type="audio/wav", size_bytes=1,
                 duration_ms=len(segmentos_spec) * 3_000, sha256="0" * 64, channels=1, sample_rate=16000,
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
        db.add(Segmento(transcricao_id=transcricao.id, falante_id=falantes[papel].id, start_ms=i * 3_000,
                        end_ms=(i + 1) * 3_000, texto_original_asr=texto, texto_revisado=texto, revisado=True))
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
