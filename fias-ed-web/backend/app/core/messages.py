from app.core.config import get_settings

_FORMAT = ("Este arquivo não parece ser um áudio MP3, WAV, M4A, AAC ou FLAC. "
           "Tente exportar o áudio novamente no gravador.")


def format_duration(seconds: int) -> str:
    minutes = seconds // 60
    hours, rest = divmod(minutes, 60)
    if hours == 0:
        return "1 minuto" if minutes == 1 else f"{minutes} minutos"
    return f"{hours}h" if rest == 0 else f"{hours}h{rest:02d}"


def format_size(num_bytes: int) -> str:
    gb = num_bytes / 1024 ** 3
    if gb >= 1:
        text = f"{gb:.1f}".rstrip("0").rstrip(".")
        return f"{text.replace('.', ',')} GB"
    return f"{round(num_bytes / 1024 ** 2)} MB"


def error_message(code: str | None) -> str | None:
    if code is None:
        return None
    s = get_settings()
    messages = {
        "AUDIO_FORMAT_MISMATCH": _FORMAT,
        "AUDIO_UNSUPPORTED_FORMAT": _FORMAT,
        "AUDIO_TOO_LONG": (f"O áudio tem mais de {format_duration(s.max_audio_seconds)}. "
                           "Divida a gravação e envie cada parte como uma aula."),
        "AUDIO_TOO_SHORT": (f"O áudio tem menos de {format_duration(s.min_audio_seconds)}. "
                            "Verifique se é o arquivo certo."),
        "AUDIO_CORRUPTED": ("Não conseguimos ler este arquivo. Ele pode estar incompleto; "
                            "tente copiá-lo de novo do gravador."),
        "AUDIO_TOO_LARGE": (f"O arquivo passa de {format_size(s.max_upload_bytes)}. Tente exportar o "
                            "áudio em MP3 ou M4A, que ocupam menos espaço."),
        "AUDIO_LOCKED": "A análise desta aula já começou. Para usar outro áudio, crie uma nova aula.",
        "AUDIO_PREPARO_FALHOU": "Não conseguimos preparar este áudio para análise. Tente enviar o arquivo de novo.",
        "AUDIO_SEM_FALA": "Não conseguimos identificar fala neste áudio. Confira se o arquivo é mesmo o da aula.",
        "DIARIZACAO_FALHOU": ("Não conseguimos separar as vozes deste áudio. "
                              "Tente enviar uma gravação com menos ruído."),
        "JOB_FAILED": ("Algo deu errado ao preparar sua aula. Tente processar novamente; "
                       "se continuar, avise o administrador."),
        "SEGMENTO_DESATUALIZADO": ("Este trecho foi alterado em outra aba. Recarregue a página "
                                   "para ver a versão atual."),
    }
    return messages.get(code, "Algo deu errado. Tente novamente.")
