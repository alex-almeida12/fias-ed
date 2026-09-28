from app.core.config import get_settings
from app.ml.protocols import ASR, Classificador, Diarizador


def obter_asr() -> ASR:
    if get_settings().usar_modelos_falsos:
        from app.ml.fakes import ASRFalso
        return ASRFalso([])
    from app.ml.asr_whisper import WhisperASR
    return WhisperASR()


def obter_diarizador() -> Diarizador:
    if get_settings().usar_modelos_falsos:
        from app.ml.fakes import DiarizadorFalso
        return DiarizadorFalso([])
    from app.ml.diar_pyannote import PyannoteDiarizador
    return PyannoteDiarizador()


def obter_classificador() -> Classificador:
    if get_settings().usar_modelos_falsos:
        from app.ml.fakes import ClassificadorFalso
        return ClassificadorFalso()
    from app.ml.clf_bertimbau import BertimbauClassificador
    return BertimbauClassificador()
