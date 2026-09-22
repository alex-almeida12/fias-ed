import uuid

import pytest

from app.audio.prepare import chunks_dir, cortar, limpar_chunks, planejar_chunks, work_path
from app.audio.storage import ensure_dirs, store_root
from app.jobs.handlers import HANDLERS
from app.jobs.queue import enqueue
from app.models import Audio
from tests.audio_fixtures import make_audio
from tests.helpers import make_aula, make_user

JANELA = 600_000


def test_aula_de_90_minutos_cobre_tudo_sem_passar_do_fim():
    duracao = 90 * 60 * 1000
    plano = planejar_chunks(duracao, JANELA)
    assert plano[0][0] == 0
    # nenhum chunk começa depois do fim do arquivo
    assert all(inicio < duracao for inicio, _ in plano)
    # a soma cobre exatamente a duração, sem sobra e sem buraco
    assert sum(d for _, d in plano) == duracao
    # o último chunk termina exatamente no fim
    ultimo_inicio, ultima_duracao = plano[-1]
    assert ultimo_inicio + ultima_duracao == duracao


def test_ultimo_chunk_incompleto_tem_a_duracao_que_sobra():
    duracao = 65 * 60 * 1000  # 65 min = 6 janelas de 10 + 5 min
    plano = planejar_chunks(duracao, JANELA)
    assert len(plano) == 7
    assert plano[-1] == (60 * 60 * 1000, 5 * 60 * 1000)


def test_aula_menor_que_a_janela_vira_um_chunk_so():
    assert planejar_chunks(7 * 60 * 1000, JANELA) == [(0, 7 * 60 * 1000)]


def test_duracao_multipla_exata_nao_cria_chunk_vazio():
    plano = planejar_chunks(3 * JANELA, JANELA)
    assert len(plano) == 3
    assert all(d > 0 for _, d in plano)


def test_duracao_invalida_recusa():
    with pytest.raises(ValueError):
        planejar_chunks(0, JANELA)


# ---- work_path / chunks_dir / cortar / limpar_chunks --------------------------------
# Não vêm dos passos do brief (que só mostra planejar_chunks, normalizar e o handler),
# mas fazem parte da lista "Produces" e chamam ffmpeg de verdade — ficariam sem
# nenhuma cobertura direta se eu não escrevesse estes três testes.

def test_work_path_e_chunks_dir_derivam_do_uuid_da_aula():
    aula_id = uuid.uuid4()
    assert work_path(aula_id).name == f"{aula_id}.wav"
    assert chunks_dir(aula_id).name == str(aula_id)


def test_cortar_gera_um_arquivo_por_pedaco_do_plano(tmp_path):
    origem = make_audio(tmp_path / "aula.wav", seconds=20)
    plano = planejar_chunks(20_000, 8_000)
    chunks = cortar(origem, plano, tmp_path / "chunks")
    assert len(chunks) == len(plano) == 3
    assert [c.indice for c in chunks] == [0, 1, 2]
    assert [(c.inicio_ms, c.duracao_ms) for c in chunks] == plano
    assert all(c.caminho.exists() and c.caminho.stat().st_size > 0 for c in chunks)


def test_limpar_chunks_apaga_o_diretorio(tmp_path):
    destino = tmp_path / "chunks"
    destino.mkdir()
    (destino / "chunk_0000.wav").write_bytes(b"x")
    limpar_chunks(destino)
    assert not destino.exists()


def test_limpar_chunks_e_silencioso_se_o_diretorio_nao_existe(tmp_path):
    limpar_chunks(tmp_path / "nao-existe")  # não levanta


# ---- handle_prepare_audio ------------------------------------------------------------

@pytest.fixture
def wav_sintetico(app_instance):
    ensure_dirs()
    destino = store_root() / "original" / f"{uuid.uuid4()}.wav"
    make_audio(destino, seconds=65)
    return destino


@pytest.fixture
def aula_validada(db, wav_sintetico):
    prof = make_user(db, "carla")
    aula = make_aula(db, prof, status="AUDIO_VALIDATED")
    db.add(Audio(aula_id=aula.id, original_filename="aula.wav", internal_filename=wav_sintetico.name,
                 path=f"original/{wav_sintetico.name}", mime_type="audio/wav",
                 size_bytes=wav_sintetico.stat().st_size, duration_ms=65_000, sha256="0" * 64,
                 channels=1, sample_rate=16000, is_original=True, derived_from_audio_id=None))
    db.commit()
    return aula


@pytest.fixture
def aula_com_audio_quebrado(db, app_instance):
    ensure_dirs()
    corrompido = store_root() / "original" / f"{uuid.uuid4()}.wav"
    corrompido.write_bytes(b"nao e um audio de verdade")
    prof = make_user(db, "denise")
    aula = make_aula(db, prof, status="AUDIO_VALIDATED")
    db.add(Audio(aula_id=aula.id, original_filename="quebrado.wav", internal_filename=corrompido.name,
                 path=f"original/{corrompido.name}", mime_type="audio/wav",
                 size_bytes=corrompido.stat().st_size, duration_ms=61_000, sha256="0" * 64,
                 channels=1, sample_rate=16000, is_original=True, derived_from_audio_id=None))
    db.commit()
    return aula


def test_prepare_audio_leva_a_preprocessing_e_nao_toca_o_original(db, aula_validada, wav_sintetico):
    original_antes = wav_sintetico.read_bytes()
    job = enqueue(db, aula_validada.id, "prepare_audio")
    db.commit()
    HANDLERS["prepare_audio"](db, job)
    db.refresh(aula_validada)
    assert aula_validada.status == "TRANSCRIBING"
    assert wav_sintetico.read_bytes() == original_antes


def test_prepare_audio_de_audio_ilegivel_vira_erro_com_mensagem_humana(db, aula_com_audio_quebrado):
    job = enqueue(db, aula_com_audio_quebrado.id, "prepare_audio")
    db.commit()
    HANDLERS["prepare_audio"](db, job)
    db.refresh(aula_com_audio_quebrado)
    assert aula_com_audio_quebrado.status == "ERROR"
    assert aula_com_audio_quebrado.error_code == "AUDIO_PREPARO_FALHOU"
