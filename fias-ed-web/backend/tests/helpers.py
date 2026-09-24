import uuid
from datetime import date

from app.auth.passwords import hash_password
from app.fias import service as fias_service
from app.ml.fakes import ClassificadorFalso
from app.models import Audio, Aula, Disciplina, Escola, Falante, Professor, Segmento, Transcricao, Turma

PASSWORD = "senha-de-teste-123"
_HASH = hash_password(PASSWORD)


def make_user(db, username: str, role: str = "PROFESSOR", *, password: str = PASSWORD,
              must_change: bool = False, active: bool = True) -> Professor:
    user = Professor(username=username, display_name=username.title(), role=role,
                     password_hash=_HASH if password == PASSWORD else hash_password(password),
                     must_change_password=must_change, is_active=active)
    db.add(user)
    db.commit()
    return user


def login(client, username: str, password: str = PASSWORD):
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    client.headers["X-CSRF-Token"] = client.cookies["fias_csrf"]
    return r


def classificar_para_triangulacao(db, aula: Aula, monkeypatch) -> None:
    """Dá a uma aula já gravada (`make_aula`/`aula_em`) transcrição, segmentos
    e uma classificação FIAS de verdade — mesmo desenho de test_padroes.py: um
    segmento do professor em categoria 5 (docente) e um do aluno, que
    `constrain_by_role` restringe para 8 ou 9 de qualquer jeito (spec §4.2).
    Roda `classificar_aula` de fato (com um classificador falso fixo no lugar
    do modelo real), para que a triangulação nunca opere sobre uma codificação
    inventada só para o teste."""
    monkeypatch.setattr(fias_service, "obter_classificador", lambda: ClassificadorFalso(categoria_fixa=5))
    audio = Audio(aula_id=aula.id, original_filename="aula.wav", internal_filename=f"{uuid.uuid4()}.wav",
                 path="original/aula.wav", mime_type="audio/wav", size_bytes=1, duration_ms=6_000,
                 sha256="0" * 64, channels=1, sample_rate=16000, is_original=True, derived_from_audio_id=None)
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
    segmentos_spec = [("PROFESSOR", "vamos começar a explicar a questão"),
                      ("ALUNO", "o que vocês acham disso")]
    for i, (papel, texto) in enumerate(segmentos_spec):
        db.add(Segmento(transcricao_id=transcricao.id, falante_id=falantes[papel].id, start_ms=i * 3_000,
                        end_ms=(i + 1) * 3_000, texto_original_asr=texto, texto_revisado=texto, revisado=True))
    db.commit()

    fias_service.classificar_aula(db, aula)
    aula.status, aula.error_code = "FIAS_COMPLETED", None
    db.commit()


def make_aula(db, professor, status: str = "DRAFT") -> Aula:
    escola = Escola(name="Escola Teste", name_key="escola teste")
    db.add(escola)
    db.flush()
    turma = Turma(escola_id=escola.id, professor_id=professor.id, name="9º Ano B")
    disciplina = Disciplina(professor_id=professor.id, name="Matemática")
    db.add_all([turma, disciplina])
    db.flush()
    aula = Aula(professor_id=professor.id, turma_id=turma.id, disciplina_id=disciplina.id,
                lesson_date=date(2026, 9, 22), status=status)
    db.add(aula)
    db.commit()
    return aula
