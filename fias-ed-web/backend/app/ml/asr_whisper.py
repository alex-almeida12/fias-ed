"""faster-whisper atrás do protocolo ASR.

`language` fixo e `temperature=0.0` não são ajuste fino: o §44 exige que a
mesma aula reprocessada dê o mesmo texto. Sem os dois o Whisper amostra a
decodificação e redetecta o idioma a cada chunk — a transcrição deixaria de
ser reprodutível, e de um jeito que nenhuma tela mostra.

O peso vem de um diretório com nome fixo dentro de models_dir.
`local_files_only=True` fecha a porta da rede no próprio carregamento: o
HF_HUB_OFFLINE=1 do compose é a segunda tranca, não a única.
"""
from pathlib import Path

from app.core.config import get_settings
from app.ml.protocols import SegmentoASR
from app.ml.registry import entrada


def diretorio_do_modelo(models_dir: str, tamanho: str) -> Path:
    return Path(models_dir) / f"faster-whisper-{tamanho}"


class WhisperASR:
    def __init__(self) -> None:
        from faster_whisper import WhisperModel
        s = get_settings()
        # O registro do shared é enraizado no diretório de experimentos e recusa
        # artefato .bin (fias-ed-shared/engine-py/tests/test_models_registry.py):
        # os pesos que vêm do Hugging Face para models_dir não cabem na lista de
        # sha256 de lá. O que dá para exigir aqui é que o modelo em uso esteja
        # declarado no registro; a integridade do arquivo é do huggingface_hub,
        # contra a revisão fixada que o próprio registro declara (integrity.repos)
        # e que scripts/setup_models.py lê de lá no download.
        entrada(s.asr_model_id)
        # device="cpu": não há GPU no alvo, e "auto" trocaria o backend conforme a
        # máquina — dois computadores dariam textos diferentes para a mesma aula.
        self._modelo = WhisperModel(str(diretorio_do_modelo(s.models_dir, s.asr_size)),
                                    device="cpu", compute_type="int8", local_files_only=True)

    def transcrever(self, caminho: Path, deslocamento_ms: int) -> list[SegmentoASR]:
        segmentos, _ = self._modelo.transcribe(str(caminho), language="pt", temperature=0.0,
                                               vad_filter=True)
        # Os tempos do chunk são relativos ao próprio chunk; quem chama espera
        # tempo global da aula, daí o deslocamento somado aqui e não depois.
        return [SegmentoASR(int(s.start * 1000) + deslocamento_ms,
                            int(s.end * 1000) + deslocamento_ms,
                            s.text.strip())
                for s in segmentos if s.text.strip()]
