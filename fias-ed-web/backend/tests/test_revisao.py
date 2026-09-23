"""PRIVACY.md exige exclusão real (remoção física, não soft delete) do material
sensível. A W2 acrescenta transcrição e segmentos: os dois primeiros testes
garantem que excluir uma aula, ou a conta do professor dono dela, apaga essas
linhas de verdade.

O resto do arquivo é a Task 9: a API da revisão da transcrição (paginação por
blocos de cinco minutos, PATCH por segmento com version otimista, conclusão da
revisão)."""
import uuid

import pytest
from sqlalchemy import select

from app.models import Audio, ClassificacaoFIAS, Falante, IndicadorFIAS, Segmento, Transcricao
from tests.helpers import login, make_aula, make_user


def _transcricao_completa(db, aula):
    """Monta a cadeia que o job de transcrição da Task 5 (ainda não implementada)
    vai deixar no banco: Transcricao, Falante, Segmento, ClassificacaoFIAS e
    IndicadorFIAS."""
    audio = Audio(aula_id=aula.id, original_filename="aula.wav",
                 internal_filename=f"{uuid.uuid4()}.wav", path="original/aula.wav",
                 mime_type="audio/wav", size_bytes=1, duration_ms=61000, sha256="0" * 64,
                 channels=1, sample_rate=16000, is_original=True)
    db.add(audio)
    db.flush()
    transcricao = Transcricao(aula_id=aula.id, audio_id=audio.id, asr_model_id="fake-asr")
    db.add(transcricao)
    db.flush()
    falante = Falante(transcricao_id=transcricao.id, diarization_label="SPEAKER_00", role="PROFESSOR")
    db.add(falante)
    db.flush()
    segmento = Segmento(transcricao_id=transcricao.id, falante_id=falante.id, start_ms=0, end_ms=1000,
                        texto_original_asr="oi turma", text_pseudonymized="oi turma")
    db.add(segmento)
    db.flush()
    db.add(ClassificacaoFIAS(segmento_id=segmento.id, transcript_source="ASR_ORIGINAL", pred_raw=1,
                             pred_role_constrained=1, confidence_raw=0.9, confidence=0.9, uncertain=False,
                             model_id="fake", rules_version="v1"))
    indicador = IndicadorFIAS(aula_id=aula.id, index_id="I1", value=0.5, numerator_count=1,
                              denominator_count=2, n_intervals=1, rules_version="v1",
                              validation_status="engineering_decision")
    db.add(indicador)
    db.commit()
    return indicador


def _segmentos_da_aula(db, aula_id):
    return (db.query(Segmento).join(Transcricao, Transcricao.id == Segmento.transcricao_id)
           .filter(Transcricao.aula_id == aula_id).all())


def test_excluir_aula_apaga_transcricao_e_segmentos(client, db):
    ana = make_user(db, "ana")
    aula = make_aula(db, ana, status="TRANSCRIBED")
    indicador_id = _transcricao_completa(db, aula).id
    login(client, "ana")
    r = client.delete(f"/api/aulas/{aula.id}")
    assert r.status_code == 204
    assert db.query(Transcricao).filter_by(aula_id=aula.id).count() == 0
    assert _segmentos_da_aula(db, aula.id) == []
    assert db.query(Falante).count() == 0
    assert db.query(ClassificacaoFIAS).count() == 0
    # IndicadorFIAS é o índice agregado de pesquisa (sem texto, sem nome, sem FK para
    # Segmento/Transcricao): o PRIVACY.md pede soft delete aqui, não remoção física,
    # para preservar o histórico necessário à reprodutibilidade científica — como já
    # acontece com Processamento.
    db.expire_all()
    assert db.get(IndicadorFIAS, indicador_id).deleted_at is not None


def test_excluir_conta_apaga_transcricoes_das_aulas(client_factory, db):
    make_user(db, "admin", role="ADMIN_LOCAL")
    admin = client_factory()
    login(admin, "admin")
    prof = make_user(db, "ana")
    aula = make_aula(db, prof, status="TRANSCRIBED")
    _transcricao_completa(db, aula)
    r = admin.request("DELETE", f"/api/admin/contas/{prof.id}", json={"confirmar_username": "ana"})
    assert r.status_code == 204
    assert db.query(Transcricao).count() == 0


# ---- Task 9: API da revisão da transcrição ----


@pytest.fixture
def client_outro_professor(client_factory, db):
    """Uma segunda professora, sem nenhuma aula — prova o isolamento por dono:
    trecho de aula de outro professor é 404, nunca 403."""
    make_user(db, "bruna")
    c = client_factory()
    login(c, "bruna")
    return c


def _aula_com_falantes(db, username, status, duration_ms=61_000):
    """A cadeia que a escolha de voz (Task 8) deixa no banco: exatamente dois
    falantes, PROFESSOR e ALUNO — nunca mais que isso, mesmo antes de qualquer
    segmento ser repontado para o ALUNO."""
    prof = make_user(db, username)
    aula = make_aula(db, prof, status=status)
    audio = Audio(aula_id=aula.id, original_filename="aula.wav", internal_filename=f"{aula.id}.wav",
                 path="original/aula.wav", mime_type="audio/wav", size_bytes=1, duration_ms=duration_ms,
                 sha256="0" * 64, channels=1, sample_rate=16000, is_original=True, derived_from_audio_id=None)
    db.add(audio)
    db.flush()
    transcricao = Transcricao(aula_id=aula.id, audio_id=audio.id, asr_model_id="fake-asr")
    db.add(transcricao)
    db.flush()
    falante_prof = Falante(transcricao_id=transcricao.id, diarization_label="SPEAKER_00", role="PROFESSOR")
    falante_aluno = Falante(transcricao_id=transcricao.id, diarization_label="merged", role="ALUNO")
    db.add_all([falante_prof, falante_aluno])
    db.flush()
    return aula, transcricao, falante_prof, falante_aluno


@pytest.fixture
def segmento_qualquer(db):
    aula, transcricao, falante_prof, _ = _aula_com_falantes(db, "carla", "READY_FOR_TRANSCRIPT_REVIEW")
    seg = Segmento(transcricao_id=transcricao.id, falante_id=falante_prof.id, start_ms=0, end_ms=1_000,
                   texto_original_asr="oi turma", text_pseudonymized="oi turma")
    db.add(seg)
    db.commit()
    return seg


@pytest.fixture
def aula_em_revisao(db):
    aula, transcricao, falante_prof, _ = _aula_com_falantes(db, "carla", "READY_FOR_TRANSCRIPT_REVIEW")
    db.add(Segmento(transcricao_id=transcricao.id, falante_id=falante_prof.id, start_ms=0, end_ms=1_000,
                    texto_original_asr="oi turma", text_pseudonymized="oi turma"))
    db.commit()
    return aula


@pytest.fixture
def aula_com_transcricao_longa(db):
    """50 minutos de áudio (10 blocos de cinco minutos), com trechos em blocos
    diferentes — a prova de que a paginação filtra de verdade, não só que a
    lista devolvida não vem vazia."""
    aula, transcricao, falante_prof, _ = _aula_com_falantes(db, "carla", "READY_FOR_TRANSCRIPT_REVIEW",
                                                             duration_ms=3_000_000)
    db.add_all([
        Segmento(transcricao_id=transcricao.id, falante_id=falante_prof.id, start_ms=0, end_ms=1_000,
                 texto_original_asr="bloco 0 a", text_pseudonymized="bloco 0 a"),
        Segmento(transcricao_id=transcricao.id, falante_id=falante_prof.id, start_ms=290_000, end_ms=299_000,
                 texto_original_asr="bloco 0 b", text_pseudonymized="bloco 0 b"),
        Segmento(transcricao_id=transcricao.id, falante_id=falante_prof.id, start_ms=300_000, end_ms=301_000,
                 texto_original_asr="bloco 1", text_pseudonymized="bloco 1"),
        Segmento(transcricao_id=transcricao.id, falante_id=falante_prof.id, start_ms=2_950_000, end_ms=2_960_000,
                 texto_original_asr="bloco 9", text_pseudonymized="bloco 9"),
    ])
    db.commit()
    return aula


@pytest.fixture
def aula_classificada(db):
    """A aula já passou pela classificação FIAS (Task 12, ainda não implementada
    nesta fatia) — o cenário do spec §3: editar um trecho agora tem que devolver a
    aula para reclassificar, porque a evidência (o texto) mudou sob um resultado
    que já foi calculado."""
    aula, transcricao, falante_prof, _ = _aula_com_falantes(db, "carla", "FIAS_COMPLETED")
    db.add(Segmento(transcricao_id=transcricao.id, falante_id=falante_prof.id, start_ms=0, end_ms=1_000,
                    texto_original_asr="oi turma", text_pseudonymized="oi turma"))
    db.commit()
    return aula


def primeiro_segmento(db, aula) -> Segmento:
    return (db.query(Segmento).join(Transcricao, Transcricao.id == Segmento.transcricao_id)
           .filter(Transcricao.aula_id == aula.id).order_by(Segmento.start_ms).first())


def test_transcricao_vem_paginada_em_blocos_de_cinco_minutos(client, aula_com_transcricao_longa):
    login(client, "carla")
    r = client.get(f"/api/aulas/{aula_com_transcricao_longa.id}/transcricao?bloco=0")
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["bloco"] == 0
    assert corpo["blocos"] == 10  # 50 min
    # não só "não vem vazio": prova que o bloco 1 e o bloco 9 ficaram de fora.
    assert {s["texto"] for s in corpo["segmentos"]} == {"bloco 0 a", "bloco 0 b"}
    assert all(s["start_ms"] < 300_000 for s in corpo["segmentos"])

    r9 = client.get(f"/api/aulas/{aula_com_transcricao_longa.id}/transcricao?bloco=9")
    assert {s["texto"] for s in r9.json()["segmentos"]} == {"bloco 9"}


def test_patch_marca_o_segmento_como_revisado_mesmo_sem_mudar_texto(client, db, segmento_qualquer):
    """`revisado` (exigido por segmento.schema.json) é "o professor já passou por
    este trecho" — diferente de `texto_revisado`, que só grava quando o texto
    muda. Confirmar um trecho como correto (PATCH só com `version`, sem `texto`
    nem `papel`) também é revisão; a tela de progresso da Task 10 depende disso."""
    login(client, "carla")
    assert segmento_qualquer.revisado is False
    r = client.patch(f"/api/segmentos/{segmento_qualquer.id}", json={"version": segmento_qualquer.version})
    assert r.status_code == 200
    assert r.json()["revisado"] is True
    db.refresh(segmento_qualquer)
    assert segmento_qualquer.revisado is True
    assert segmento_qualquer.texto_revisado is None  # nada mudou no texto


def test_editar_texto_regrava_a_versao_pseudonimizada(client, db, segmento_qualquer):
    login(client, "carla")
    r = client.patch(f"/api/segmentos/{segmento_qualquer.id}",
                     json={"texto": "a Maria respondeu", "version": segmento_qualquer.version})
    assert r.status_code == 200
    db.refresh(segmento_qualquer)
    assert segmento_qualquer.texto_revisado == "a Maria respondeu"
    assert "Maria" not in segmento_qualquer.text_pseudonymized
    assert "[NOME]" in segmento_qualquer.text_pseudonymized


def test_texto_com_caracteres_especiais_volta_literal(client, segmento_qualquer):
    """Review Focus 3: o texto vai para a tela e, na W3, para o relatório — tem
    que voltar literal, sem escapar duas vezes e sem virar código."""
    login(client, "carla")
    texto = 'ele disse "3 < 5" e riu 😄'
    r = client.patch(f"/api/segmentos/{segmento_qualquer.id}",
                     json={"texto": texto, "version": segmento_qualquer.version})
    assert r.status_code == 200
    assert r.json()["texto"] == texto


def test_segunda_aba_nao_sobrescreve_a_primeira_em_silencio(client, db, segmento_qualquer):
    """Review Focus 5: duas abas editando o mesmo segmento. Não basta a segunda
    escrita levar 409 — o texto da primeira precisa continuar valendo, ou a
    "proteção" seria só um código de status sem efeito real."""
    login(client, "carla")
    versao = segmento_qualquer.version
    primeira = client.patch(f"/api/segmentos/{segmento_qualquer.id}",
                            json={"texto": "primeira", "version": versao})
    assert primeira.status_code == 200
    segunda = client.patch(f"/api/segmentos/{segmento_qualquer.id}",
                           json={"texto": "segunda", "version": versao})
    assert segunda.status_code == 409
    assert segunda.json()["error_code"] == "SEGMENTO_DESATUALIZADO"
    db.refresh(segmento_qualquer)
    assert segmento_qualquer.texto_revisado == "primeira"


def test_trocar_papel_de_um_segmento(client, db, segmento_qualquer):
    """Trocar o falante de um trecho é apontar para a linha ALUNO já existente,
    não criar uma linha nova (Falante tem exatamente duas linhas depois da
    escolha da voz) — por isso a prova é pelo id da linha e pela contagem, não
    só pelo valor de `role`."""
    login(client, "carla")
    aluno = db.scalar(select(Falante).where(Falante.transcricao_id == segmento_qualquer.transcricao_id,
                                            Falante.role == "ALUNO"))
    r = client.patch(f"/api/segmentos/{segmento_qualquer.id}",
                     json={"papel": "ALUNO", "version": segmento_qualquer.version})
    assert r.status_code == 200
    assert r.json()["papel"] == "ALUNO"
    db.refresh(segmento_qualquer)
    assert segmento_qualquer.falante_id == aluno.id
    assert db.query(Falante).filter_by(transcricao_id=segmento_qualquer.transcricao_id).count() == 2


def test_editar_depois_do_fias_devolve_a_aula_para_reclassificar(client, db, aula_classificada):
    """spec §3: evidência e resultado não podem ficar fora de sincronia. Sem isto,
    a tela de padrões seguiria mostrando a classificação do texto antigo."""
    login(client, "carla")
    seg = primeiro_segmento(db, aula_classificada)
    r = client.patch(f"/api/segmentos/{seg.id}", json={"texto": "corrigido", "version": seg.version})
    assert r.status_code == 200
    db.refresh(aula_classificada)
    assert aula_classificada.status == "READY_FOR_FIAS"
    assert aula_classificada.error_code is None


def test_editar_antes_do_fias_nao_muda_o_status(client, db, aula_em_revisao):
    """Só a aula já classificada volta atrás; a que ainda está em revisão fica
    onde está — não é qualquer edição que reabre, é editar DEPOIS da classificação."""
    login(client, "carla")
    seg = primeiro_segmento(db, aula_em_revisao)
    antes = aula_em_revisao.status
    r = client.patch(f"/api/segmentos/{seg.id}", json={"texto": "x", "version": seg.version})
    assert r.status_code == 200
    db.refresh(aula_em_revisao)
    assert aula_em_revisao.status == antes


def test_confirmar_sem_editar_nao_reabre_a_classificacao(client, db, aula_classificada):
    """Só uma mudança de conteúdo (texto ou papel) invalida a classificação —
    marcar um trecho como revisado sem alterar nada (PATCH só com `version`) não
    é evidência nova, não deveria mandar a aula de volta para reclassificar."""
    login(client, "carla")
    seg = primeiro_segmento(db, aula_classificada)
    r = client.patch(f"/api/segmentos/{seg.id}", json={"version": seg.version})
    assert r.status_code == 200
    db.refresh(aula_classificada)
    assert aula_classificada.status == "FIAS_COMPLETED"


def test_concluir_a_revisao_leva_a_ready_for_fias(client, db, aula_em_revisao):
    login(client, "carla")
    r = client.post(f"/api/aulas/{aula_em_revisao.id}/transcricao/concluir")
    assert r.status_code == 200
    assert r.json()["status"] == "READY_FOR_FIAS"
    db.refresh(aula_em_revisao)
    assert aula_em_revisao.status == "READY_FOR_FIAS"


def test_segmento_de_outro_professor_da_404(client_outro_professor, segmento_qualquer):
    r = client_outro_professor.patch(f"/api/segmentos/{segmento_qualquer.id}",
                                     json={"texto": "x", "version": 1})
    assert r.status_code == 404
    assert r.json()["error_code"] == "SEGMENTO_NAO_ENCONTRADO"
