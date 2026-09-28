""""Qual destas vozes é você?" — Task 8.

aula_diarizada simula o estado em que handle_diarize (Task 7) deixa a aula:
dois falantes provisórios (role=UNASSIGNED), cada um com os segmentos já
repontados para a sua voz, status READY_FOR_SPEAKER_REVIEW. A voz "SPEAKER_00"
fala mais (70s em 3 segmentos) que "SPEAKER_01" (20s em 1 segmento), então ela
vira "voz-1" — a ordem de numeração não é arbitrária, é por tempo de fala.

`cliente` já está autenticado como a professora dona de `aula_diarizada`
(dependência de fixture: `aula_diarizada` usa `cliente` para pegar a mesma
professora). `cliente_outro_professor` é uma segunda professora, sem
nenhuma aula, para provar o isolamento por dono.
"""
import pytest
from sqlalchemy import delete, select

from app.models import Audio, Falante, Professor, Segmento, Transcricao
from app.transcricao.service import transcricao_da_aula
from tests.helpers import login, make_aula, make_user


@pytest.fixture
def cliente(client_factory, db):
    make_user(db, "carla")
    c = client_factory()
    login(c, "carla")
    return c


@pytest.fixture
def cliente_outro_professor(client_factory, db):
    make_user(db, "bruna")
    c = client_factory()
    login(c, "bruna")
    return c


@pytest.fixture
def aula_diarizada(db, cliente):
    prof = db.scalar(select(Professor).where(Professor.username == "carla"))
    aula = make_aula(db, prof, status="READY_FOR_SPEAKER_REVIEW")
    audio = Audio(aula_id=aula.id, original_filename="aula.wav", internal_filename=f"{aula.id}.wav",
                 path="original/aula.wav", mime_type="audio/wav", size_bytes=1, duration_ms=100_000,
                 sha256="0" * 64, channels=1, sample_rate=16000, is_original=True, derived_from_audio_id=None)
    db.add(audio)
    db.flush()
    transcricao = Transcricao(aula_id=aula.id, audio_id=audio.id, asr_model_id="fake-asr")
    db.add(transcricao)
    db.flush()
    voz_que_fala_mais = Falante(transcricao_id=transcricao.id, diarization_label="SPEAKER_00", role="UNASSIGNED")
    voz_que_fala_menos = Falante(transcricao_id=transcricao.id, diarization_label="SPEAKER_01", role="UNASSIGNED")
    db.add_all([voz_que_fala_mais, voz_que_fala_menos])
    db.flush()
    db.add_all([
        Segmento(transcricao_id=transcricao.id, falante_id=voz_que_fala_mais.id, start_ms=0, end_ms=30_000,
                 texto_original_asr="a", text_pseudonymized="a"),
        Segmento(transcricao_id=transcricao.id, falante_id=voz_que_fala_mais.id, start_ms=30_000, end_ms=60_000,
                 texto_original_asr="b", text_pseudonymized="b"),
        Segmento(transcricao_id=transcricao.id, falante_id=voz_que_fala_mais.id, start_ms=60_000, end_ms=70_000,
                 texto_original_asr="c", text_pseudonymized="c"),
        Segmento(transcricao_id=transcricao.id, falante_id=voz_que_fala_menos.id, start_ms=70_000, end_ms=90_000,
                 texto_original_asr="d", text_pseudonymized="d"),
    ])
    db.commit()
    return aula


def segmentos_da(db, aula):
    """Segmentos da aula, com `.falante` já resolvido (join manual, não uma
    relationship do modelo — o schema do shared não declara uma)."""
    t = transcricao_da_aula(db, aula.id)
    falantes = {f.id: f for f in db.scalars(select(Falante).where(Falante.transcricao_id == t.id)).all()}
    linhas = db.scalars(select(Segmento).where(Segmento.transcricao_id == t.id)
                        .order_by(Segmento.start_ms)).all()
    for linha in linhas:
        linha.falante = falantes[linha.falante_id]
    return linhas


def falantes_da(db, aula):
    t = transcricao_da_aula(db, aula.id)
    return db.scalars(select(Falante).where(Falante.transcricao_id == t.id)).all()


def test_vozes_sao_numeradas_por_tempo_de_fala_e_nunca_chamadas_de_aluno(cliente, aula_diarizada):
    r = cliente.get(f"/api/aulas/{aula_diarizada.id}/vozes")
    assert r.status_code == 200
    vozes = r.json()["vozes"]
    rotulos = [v["rotulo"] for v in vozes]
    assert rotulos == ["voz-1", "voz-2"]
    assert not any("aluno" in x.lower() or "speaker" in x.lower() for x in rotulos)


def test_vozes_traz_tempo_contagem_e_amostras_corretos(cliente, aula_diarizada):
    """Prova os números, não só os rótulos — um cálculo errado de tempo total,
    contagem de segmentos ou amostras passaria pelo teste anterior sem ser
    detectado."""
    r = cliente.get(f"/api/aulas/{aula_diarizada.id}/vozes")
    vozes = r.json()["vozes"]
    voz1, voz2 = vozes
    assert voz1["tempo_total_ms"] == 70_000
    assert voz1["n_segmentos"] == 3
    assert voz1["amostras"] == [{"inicio_ms": 0, "fim_ms": 30_000},
                                {"inicio_ms": 30_000, "fim_ms": 60_000},
                                {"inicio_ms": 60_000, "fim_ms": 70_000}]
    assert voz2["tempo_total_ms"] == 20_000
    assert voz2["n_segmentos"] == 1
    assert voz2["amostras"] == [{"inicio_ms": 70_000, "fim_ms": 90_000}]


def test_escolher_voz_atribui_os_segmentos_da_voz_escolhida_ao_professor_e_o_resto_a_aluno(
        cliente, db, aula_diarizada):
    """Mais forte que só checar `{papeis} == {"PROFESSOR", "ALUNO"}` — isso
    passaria mesmo se a implementação trocasse os dois grupos, ou mandasse
    tudo para ALUNO menos um segmento qualquer. Aqui a prova é por segmento:
    exatamente os da voz-1 (a, b, c) viram PROFESSOR; o resto (d) vira ALUNO."""
    r = cliente.post(f"/api/aulas/{aula_diarizada.id}/vozes/escolher", json={"rotulo": "voz-1"})
    assert r.status_code == 200
    papel_por_texto = {s.texto_original_asr: s.falante.role for s in segmentos_da(db, aula_diarizada)}
    assert papel_por_texto == {"a": "PROFESSOR", "b": "PROFESSOR", "c": "PROFESSOR", "d": "ALUNO"}


def test_escolher_a_outra_voz_inverte_quem_e_professor(cliente, db, aula_diarizada):
    """Sem isto, uma implementação que sempre marcasse a voz que mais fala como
    PROFESSOR (ignorando o `rotulo` do corpo da requisição) passaria pelo teste
    anterior sem nunca ler `body.rotulo`."""
    r = cliente.post(f"/api/aulas/{aula_diarizada.id}/vozes/escolher", json={"rotulo": "voz-2"})
    assert r.status_code == 200
    papel_por_texto = {s.texto_original_asr: s.falante.role for s in segmentos_da(db, aula_diarizada)}
    assert papel_por_texto == {"a": "ALUNO", "b": "ALUNO", "c": "ALUNO", "d": "PROFESSOR"}


def test_escolher_voz_apaga_os_rotulos_do_diarizador(cliente, db, aula_diarizada):
    """§48: o agrupamento por voz existe só entre a diarização e a escolha.
    Depois disso não pode sobrar nada dele no banco."""
    cliente.post(f"/api/aulas/{aula_diarizada.id}/vozes/escolher", json={"rotulo": "voz-1"})
    falantes = falantes_da(db, aula_diarizada)
    papeis = {f.role for f in falantes}
    assert papeis == {"PROFESSOR", "ALUNO"}
    assert len(falantes) == 2
    aluno = next(f for f in falantes if f.role == "ALUNO")
    assert aluno.diarization_label == "merged"


def test_escolher_voz_leva_a_revisao_da_transcricao(cliente, db, aula_diarizada):
    cliente.post(f"/api/aulas/{aula_diarizada.id}/vozes/escolher", json={"rotulo": "voz-1"})
    db.refresh(aula_diarizada)
    assert aula_diarizada.status == "READY_FOR_TRANSCRIPT_REVIEW"


def test_com_uma_voz_so_a_escolha_ainda_cria_o_aluno_sem_segmentos(cliente, db, aula_diarizada):
    """Task 7 decidiu que uma aula com uma voz só não é erro (aula expositiva
    legítima). A escolha de voz precisa continuar valendo nesse caso — o
    produto promete exatamente duas linhas Falante depois da escolha, mesmo
    quando o ALUNO não corresponde a segmento nenhum."""
    t = transcricao_da_aula(db, aula_diarizada.id)
    voz2 = db.scalar(select(Falante).where(Falante.transcricao_id == t.id,
                                           Falante.diarization_label == "SPEAKER_01"))
    db.execute(delete(Segmento).where(Segmento.falante_id == voz2.id))
    db.execute(delete(Falante).where(Falante.id == voz2.id))
    db.commit()
    r = cliente.post(f"/api/aulas/{aula_diarizada.id}/vozes/escolher", json={"rotulo": "voz-1"})
    assert r.status_code == 200
    papeis = {f.role for f in falantes_da(db, aula_diarizada)}
    assert papeis == {"PROFESSOR", "ALUNO"}


def test_rotulo_inexistente_recusa(cliente, aula_diarizada):
    r = cliente.post(f"/api/aulas/{aula_diarizada.id}/vozes/escolher", json={"rotulo": "voz-99"})
    assert r.status_code == 422
    assert r.json()["error_code"] == "VOZ_INVALIDA"


def test_aula_fora_do_estado_de_escolha_recusa(cliente, db, aula_diarizada):
    aula_diarizada.status = "READY_FOR_TRANSCRIPT_REVIEW"
    db.commit()
    r = cliente.post(f"/api/aulas/{aula_diarizada.id}/vozes/escolher", json={"rotulo": "voz-1"})
    assert r.status_code == 409
    assert r.json()["error_code"] == "AULA_STATE"


def test_aula_de_outro_professor_da_404_na_listagem_e_na_escolha(cliente_outro_professor, aula_diarizada):
    r1 = cliente_outro_professor.get(f"/api/aulas/{aula_diarizada.id}/vozes")
    assert r1.status_code == 404 and r1.json()["error_code"] == "AULA_NAO_ENCONTRADA"
    r2 = cliente_outro_professor.post(f"/api/aulas/{aula_diarizada.id}/vozes/escolher", json={"rotulo": "voz-1"})
    assert r2.status_code == 404 and r2.json()["error_code"] == "AULA_NAO_ENCONTRADA"
