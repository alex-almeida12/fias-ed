"""PRIVACY.md exige exclusão real (remoção física, não soft delete) do material
sensível. A W2 acrescenta transcrição e segmentos: este teste garante que excluir
uma aula, ou a conta do professor dono dela, apaga essas linhas de verdade."""
import uuid

from app.models import ClassificacaoFIAS, Falante, IndicadorFIAS, Segmento, Transcricao
from tests.helpers import login, make_aula, make_user


def _transcricao_completa(db, aula):
    """Monta a cadeia que o job de transcrição da Task 5 (ainda não implementada)
    vai deixar no banco: Transcricao, Falante, Segmento, ClassificacaoFIAS e
    IndicadorFIAS."""
    from app.models import Audio

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
