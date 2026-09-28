"""Job de diarização: cruza os segmentos já gravados com os turnos que o
separador de vozes devolve, repontando cada segmento para o falante da sua
voz. Falha do separador é erro de produto (§48 exige mensagem humana, não
degradação silenciosa); uma única voz detectada não é erro — pode ser uma
aula expositiva legítima.

A fixture aula_transcrita vive em conftest.py — é compartilhada com
test_align.py, que também precisa do estado "pós-transcrição, pré-diarização"
para testar o repontamento contra o banco de verdade."""
import pytest

from app.audio.prepare import work_path
from app.core.db import SessionLocal, get_engine
from app.jobs import handlers
from app.jobs.handlers import HANDLERS
from app.jobs.queue import enqueue
from app.ml.fakes import DiarizadorFalso
from app.ml.protocols import TurnoDiar
from app.models import Aula, Falante, Segmento
from app.transcricao.service import transcricao_da_aula


@pytest.fixture
def diarizador_falso_duas_vozes(monkeypatch):
    diarizador = DiarizadorFalso([TurnoDiar(0, 4_500, "SPEAKER_00"), TurnoDiar(4_500, 9_000, "SPEAKER_01")])
    monkeypatch.setattr(handlers, "obter_diarizador", lambda: diarizador)
    return diarizador


@pytest.fixture
def diarizador_falso_uma_voz(monkeypatch):
    diarizador = DiarizadorFalso([TurnoDiar(0, 9_000, "SPEAKER_00")])
    monkeypatch.setattr(handlers, "obter_diarizador", lambda: diarizador)
    return diarizador


@pytest.fixture
def diarizador_que_falha(monkeypatch):
    class DiarizadorQueFalha:
        def turnos(self, caminho):
            raise RuntimeError("modelo indisponível")

    monkeypatch.setattr(handlers, "obter_diarizador", lambda: DiarizadorQueFalha())


def _rodar(db, aula):
    job = enqueue(db, aula.id, "diarize")
    db.commit()
    HANDLERS["diarize"](db, job)


def test_diarizing_so_existe_enquanto_a_diarizacao_acontece(db, aula_transcrita, monkeypatch):
    """A aula chega aqui em TRANSCRIBED e continua assim enquanto o job estiver na
    fila — atrás de outras aulas, com um worker só. DIARIZING é marcado por este
    handler ao começar, e é visível de outra sessão (já commitado) durante o
    trabalho, que é o que a tela do professor lê. Olhar só o status final não
    distinguiria isto de marcar no fim do handler anterior."""
    visto: list[str] = []

    class DiarizadorEspiao:
        def turnos(self, caminho):
            with SessionLocal(bind=get_engine()) as outra:
                visto.append(outra.get(Aula, aula_transcrita.id).status)
            return [TurnoDiar(0, 9_000, "SPEAKER_00")]

    monkeypatch.setattr(handlers, "obter_diarizador", lambda: DiarizadorEspiao())
    job = enqueue(db, aula_transcrita.id, "diarize")
    db.commit()
    assert db.get(Aula, aula_transcrita.id).status == "TRANSCRIBED"
    HANDLERS["diarize"](db, job)
    assert visto == ["DIARIZING"]
    db.refresh(aula_transcrita)
    assert aula_transcrita.status == "READY_FOR_SPEAKER_REVIEW"


def test_diarize_leva_a_escolha_de_voz(db, aula_transcrita, diarizador_falso_duas_vozes):
    _rodar(db, aula_transcrita)
    db.refresh(aula_transcrita)
    assert aula_transcrita.status == "READY_FOR_SPEAKER_REVIEW"
    assert aula_transcrita.error_code is None


def test_diarize_nao_grava_agrupamento_de_voz_persistente(db, aula_transcrita, diarizador_falso_duas_vozes):
    """§48: nenhum agrupamento por estudante sobrevive além de UNASSIGNED —
    Falante só conhece PROFESSOR, ALUNO e UNASSIGNED como papel."""
    _rodar(db, aula_transcrita)
    t = transcricao_da_aula(db, aula_transcrita.id)
    falantes = db.query(Falante).filter_by(transcricao_id=t.id).all()
    assert falantes  # a diarização criou ao menos um falante por voz
    assert {f.role for f in falantes} <= {"PROFESSOR", "ALUNO", "UNASSIGNED"}


def test_diarize_repointa_os_segmentos_para_a_voz_certa_e_apaga_o_provisorio(
        db, aula_transcrita, diarizador_falso_duas_vozes):
    _rodar(db, aula_transcrita)
    t = transcricao_da_aula(db, aula_transcrita.id)
    linhas = db.query(Segmento).filter_by(transcricao_id=t.id).order_by(Segmento.start_ms).all()
    falantes = {f.id: f.diarization_label for f in db.query(Falante).filter_by(transcricao_id=t.id).all()}
    assert [falantes[s.falante_id] for s in linhas] == ["SPEAKER_00", "SPEAKER_01"]
    # o provisório da Task 5 não tem mais segmentos apontando para ele: some.
    assert db.query(Falante).filter_by(transcricao_id=t.id, diarization_label="pendente").count() == 0


def test_uma_voz_so_nao_e_erro(db, aula_transcrita, diarizador_falso_uma_voz):
    _rodar(db, aula_transcrita)
    db.refresh(aula_transcrita)
    assert aula_transcrita.status == "READY_FOR_SPEAKER_REVIEW"


def test_falha_da_diarizacao_vira_erro_com_mensagem_humana(db, aula_transcrita, diarizador_que_falha):
    _rodar(db, aula_transcrita)
    db.refresh(aula_transcrita)
    assert aula_transcrita.status == "ERROR"
    assert aula_transcrita.error_code == "DIARIZACAO_FALHOU"


def test_job_para_aula_excluida_e_fechado_sem_diarizar(db, aula_transcrita, diarizador_falso_duas_vozes):
    from app.models import utcnow
    aula_transcrita.deleted_at = utcnow()
    db.commit()
    job = enqueue(db, aula_transcrita.id, "diarize")
    db.commit()
    HANDLERS["diarize"](db, job)
    db.refresh(job)
    assert job.status == "done"


# ---- ciclo de vida da cópia de trabalho --------------------------------------------


def _criar_trabalho(aula):
    caminho = work_path(aula.id)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_bytes(b"RIFF")
    return caminho


def test_diarize_apaga_a_copia_de_trabalho_ao_terminar(db, aula_transcrita, diarizador_falso_duas_vozes):
    """A diarização é o último estágio que lê o arquivo normalizado: a revisão de
    vozes ouve trechos do áudio ORIGINAL e a classificação só vê texto. Enquanto
    ninguém apagava aqui, cada aula processada deixava a cópia em disco para
    sempre — ~173 MB numa aula de 90 min."""
    caminho = _criar_trabalho(aula_transcrita)
    _rodar(db, aula_transcrita)
    db.refresh(aula_transcrita)
    assert aula_transcrita.status == "READY_FOR_SPEAKER_REVIEW"
    assert not caminho.exists()


def test_diarize_so_apaga_depois_de_fechar_o_job(db, aula_transcrita, monkeypatch):
    """A ordem importa por causa do retry: um job ainda aberto pode voltar à fila
    (`recover_stale`) e o handler reprocessa o estágio do início, lendo este
    arquivo de novo. Se o arquivo sumisse antes do commit, o reprocessamento
    encontraria o disco vazio."""
    caminho = _criar_trabalho(aula_transcrita)
    visto = {}

    class DiarizadorEspiao:
        def turnos(self, caminho_recebido):
            visto["existia_durante"] = caminho_recebido.exists()
            return [TurnoDiar(0, 9_000, "SPEAKER_00")]

    monkeypatch.setattr(handlers, "obter_diarizador", lambda: DiarizadorEspiao())
    job = enqueue(db, aula_transcrita.id, "diarize")
    db.commit()
    HANDLERS["diarize"](db, job)
    db.refresh(job)
    assert visto["existia_durante"] is True
    assert job.status == "done" and not caminho.exists()


def test_diarize_que_falha_nao_deixa_a_copia_de_trabalho(db, aula_transcrita, diarizador_que_falha):
    """`fail_job` é terminal: a aula vai para ERROR e não volta ao pipeline sem um
    áudio novo, que refaz a normalização. Ninguém mais vai ler este arquivo."""
    caminho = _criar_trabalho(aula_transcrita)
    _rodar(db, aula_transcrita)
    db.refresh(aula_transcrita)
    assert aula_transcrita.error_code == "DIARIZACAO_FALHOU"
    assert not caminho.exists()


# ---- evidência de fala/não-fala -----------------------------------------------------


def test_diarize_grava_a_linha_do_tempo_de_fala(db, aula_transcrita, diarizador_falso_duas_vozes):
    """A cópia de trabalho do áudio some no fim deste job, e a classificação
    FIAS só roda depois da revisão de vozes. Se a linha do tempo de fala não
    ficar gravada aqui, a regra 4 de Flanders (silêncio de 3 s ou mais =
    categoria 10) perde para sempre a única fonte de "onde não houve fala"."""
    from app.models import TrechoDeFala
    _rodar(db, aula_transcrita)
    t = transcricao_da_aula(db, aula_transcrita.id)
    trechos = db.query(TrechoDeFala).filter_by(transcricao_id=t.id).order_by(
        TrechoDeFala.inicio_ms).all()
    # duas vozes em sequência, uma de cada vez: uma linha só, de uma voz —
    # a troca de turno entre elas não sobrevive à fusão, e é isso que se quer.
    assert [(x.inicio_ms, x.fim_ms, x.n_vozes) for x in trechos] == [(0, 9_000, 1)]


def test_diarize_nao_grava_o_rotulo_da_voz_em_lugar_nenhum(db, aula_transcrita,
                                                           diarizador_falso_duas_vozes):
    """§48: não existe agrupamento de voz por estudante em lugar nenhum, nem no
    banco. Com (início, fim, rótulo) gravados, "a voz 01 falou nestes momentos
    da aula" sairia de um SELECT — e é exatamente isso que a LGPD veda aqui. O
    que fica é quando houve fala e quantas vozes, nunca quais."""
    from app.models import TrechoDeFala
    _rodar(db, aula_transcrita)
    t = transcricao_da_aula(db, aula_transcrita.id)
    colunas = {c.name for c in TrechoDeFala.__table__.columns}
    assert "rotulo" not in colunas and "diarization_label" not in colunas
    trechos = db.query(TrechoDeFala).filter_by(transcricao_id=t.id).all()
    valores = {str(v) for x in trechos for v in (x.inicio_ms, x.fim_ms, x.n_vozes)}
    assert not any("SPEAKER" in v for v in valores)


def test_vozes_simultaneas_sao_contadas_sem_dizer_quais(db, aula_transcrita, monkeypatch):
    """A contagem é o que a confusão vai precisar (fias_rules.confusion, ainda
    não implementada), e é o máximo que dá para guardar sem reidentificar."""
    from app.models import TrechoDeFala
    diarizador = DiarizadorFalso([TurnoDiar(0, 6_000, "SPEAKER_00"),
                                  TurnoDiar(3_000, 9_000, "SPEAKER_01")])
    monkeypatch.setattr(handlers, "obter_diarizador", lambda: diarizador)
    _rodar(db, aula_transcrita)
    t = transcricao_da_aula(db, aula_transcrita.id)
    trechos = db.query(TrechoDeFala).filter_by(transcricao_id=t.id).order_by(
        TrechoDeFala.inicio_ms).all()
    assert [(x.inicio_ms, x.fim_ms, x.n_vozes) for x in trechos] == [
        (0, 3_000, 1), (3_000, 6_000, 2), (6_000, 9_000, 1)]


def test_reprocessar_a_diarizacao_nao_duplica_a_linha_do_tempo(db, aula_transcrita,
                                                               diarizador_falso_duas_vozes):
    """`recover_stale` devolve um job travado à fila e o handler refaz o estágio
    do início. Trecho duplicado viraria fala onde não houve — e silêncio a menos."""
    from app.models import TrechoDeFala
    _rodar(db, aula_transcrita)
    _rodar(db, aula_transcrita)
    t = transcricao_da_aula(db, aula_transcrita.id)
    assert db.query(TrechoDeFala).filter_by(transcricao_id=t.id).count() == 1
