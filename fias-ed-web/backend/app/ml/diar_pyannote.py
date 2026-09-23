"""pyannote.audio atrás do protocolo Diarizador.

O pipeline carrega de um config.yaml local, escrito pelo setup, cujos campos
`segmentation` e `embedding` já apontam para arquivos em disco. O config.yaml
publicado no Hugging Face aponta para outros dois repositórios pelo id;
carregado como vem, o pipeline sai para a rede — e em execução não há rede
(HF_HUB_OFFLINE=1).
"""
from pathlib import Path

from app.core.config import get_settings
from app.ml.protocols import TurnoDiar
from app.ml.registry import entrada


class PyannoteDiarizador:
    def __init__(self) -> None:
        from pyannote.audio import Pipeline
        s = get_settings()
        # O registro do shared é enraizado no diretório de experimentos e recusa
        # artefato .bin (fias-ed-shared/engine-py/tests/test_models_registry.py):
        # os pesos que vêm do Hugging Face para models_dir não cabem na lista de
        # sha256 de lá. O que dá para exigir aqui é que o modelo em uso esteja
        # declarado no registro; a integridade do arquivo é do huggingface_hub,
        # contra a revisão fixada em scripts/setup_models.py.
        entrada(s.diar_model_id)
        config = Path(s.models_dir) / "pyannote" / "config.yaml"
        if not config.is_file():
            raise FileNotFoundError(f"pipeline de diarização ausente: {config}")
        self._pipeline = Pipeline.from_pretrained(config)

    def turnos(self, caminho: Path) -> list[TurnoDiar]:
        # Sem num_speakers: numa sala não se sabe quantas vozes vão aparecer.
        anotacao = self._pipeline(str(caminho))
        turnos = [TurnoDiar(int(seg.start * 1000), int(seg.end * 1000), rotulo)
                  for seg, _, rotulo in anotacao.itertracks(yield_label=True)]
        return sorted(turnos, key=lambda t: t.inicio_ms)
