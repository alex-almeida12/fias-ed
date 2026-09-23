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
from app.ml.registry import entrada_adotavel


def _permitir_globais_dos_checkpoints() -> None:
    """Deixa o `weights_only=True` do torch aceitar os dois checkpoints do pyannote.

    Desde o torch 2.6 o `torch.load` desempacota com `weights_only=True`, que só
    reconstrói tensores e tipos de uma lista curta. Os checkpoints do pyannote
    guardam, ao lado dos pesos, a versão do torch que os gravou e as
    `Specifications` da tarefa — quatro tipos que não estão nessa lista. Sem
    declará-los, o carregamento morre em `UnpicklingError` antes de tocar num
    peso, e a diarização inteira fica indisponível.

    A saída fácil seria `weights_only=False`, que volta ao pickle irrestrito e
    executa o que o arquivo mandar. Não é aceitável aqui: é o mesmo motivo pelo
    qual o registro do BERTimbau recusa artefato `.bin`. Estes quatro tipos são
    inertes (uma string de versão, dois `Enum` e uma dataclass); declarar só
    eles mantém a checagem ligada para todo o resto do arquivo.
    """
    import torch
    from pyannote.audio.core.task import Problem, Resolution, Specifications
    from torch.torch_version import TorchVersion

    torch.serialization.add_safe_globals(
        [TorchVersion, Problem, Resolution, Specifications])


class PyannoteDiarizador:
    def __init__(self) -> None:
        from pyannote.audio import Pipeline
        s = get_settings()
        _permitir_globais_dos_checkpoints()
        # O registro do shared é enraizado no diretório de experimentos e recusa
        # artefato .bin (fias-ed-shared/engine-py/tests/test_models_registry.py):
        # os pesos que vêm do Hugging Face para models_dir não cabem na lista de
        # sha256 de lá. O que dá para exigir aqui é que o modelo em uso esteja
        # declarado no registro; a integridade do arquivo é do huggingface_hub,
        # contra a revisão fixada que o próprio registro declara (integrity.repos)
        # e que scripts/setup_models.py lê de lá no download.
        # `entrada_adotavel`: o registro também guarda modelo que existe só pela
        # procedência de uma medição (§21), e esse não pode ser carregado.
        entrada_adotavel(s.diar_model_id)
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
