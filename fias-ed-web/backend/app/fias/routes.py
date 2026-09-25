"""Rota da Task 13: "padrões de interação" — a tela em que o professor lê o
que o FIAS encontrou na própria aula.

A ordem dos campos na resposta segue a ordem de leitura da tela (spec §8.4):
faixa de tempo e observações primeiro — o que ajuda a entender —, matriz e
índices depois — o dado técnico.

Faixa e matriz NÃO são persistidas (ruling da Task 12: "transition_matrix não
é chamada — não há onde guardar e a Task 13 recalcula"): remontadas aqui a
partir de `ClassificacaoFIAS`/`Segmento`, com as mesmas funções do motor que a
classificação usa (`code_lesson`, `transition_matrix`) — nenhuma regra
científica é reimplementada, nem a aritmética de quando cada marca começa e
acaba. Os índices, ao contrário, já estão
persistidos em `IndicadorFIAS` pela Task 12: esta rota só lê, nunca recalcula.

Nenhuma observação ou descrição de índice compara um número a um limiar: os
limiares do MTSS estão `PENDING_SCIENTIFIC_VALIDATION` (spec §8.4) e um
veredito ali seria inventado. MTSS, triangulação e recomendações estão fora do
escopo da W2 (spec §12) — as "observações" aqui são fatos sobre categorias que
de fato ocorreram na aula, cada uma ancorada em evidência real
(`select_evidence_segments`, do motor — sem heurística de seleção própria),
não interpretação pedagógica.
"""
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from fias_ed_engine.intervals import Mark, transition_matrix
from fias_ed_engine.mtss import select_evidence_segments
from fias_ed_engine.rules import load_rules

from app.audit import audit
from app.auth.deps import Actor, current_actor
from app.aulas.service import get_owned_aula
from app.core.db import get_db
from app.core.errors import AppError
from app.fias.service import codificacao_da_aula
from app.models import ClassificacaoFIAS, IndicadorFIAS, Segmento
from app.transcricao.service import POS_CLASSIFICACAO, texto_efetivo, transcricao_da_aula

router = APIRouter()

# Nome em português de cada grupo FIAS, na nomenclatura que fias-ed-shared/
# design-tokens/tokens.json já usa para as cores da faixa de tempo (indirect/
# direct/student/silence → --color-fias-*). A categoria 1-10 → grupo vem de
# rules["categories"] (campos group/influence), não de uma tabela paralela:
# se uma categoria mudar de grupo no shared, a tela acompanha sem tocar aqui.
_GRUPO_PT = {"indirect": "indireta", "direct": "direta", "student": "estudante", "silence": "silêncio"}


def _grupo_por_categoria(rules: dict) -> dict[int, str]:
    grupos: dict[int, str] = {}
    for cat in rules["categories"]:
        chave = cat["influence"] if cat["group"] == "teacher" else cat["group"]
        grupos[cat["id"]] = _GRUPO_PT[chave]
    return grupos


def _faixa(marcas: list[Mark], rules: dict) -> list[dict]:
    """Os tempos vêm da marca, nunca de `índice × passo`.

    A conta antiga (`i * passo_ms`) pressupunha uma marca por intervalo de 3 s.
    Desde que o motor passou a registrar toda mudança de categoria (regra 3 de
    Flanders), a sequência é mais longa que `duração / 3 s` — 549 marcas contra
    482 na aula medida — e a faixa pintava 3,3 min além do fim da aula, com o
    último trecho começando depois do fim. Quem sabe quando cada marca começa e
    acaba é o motor, e é ele quem diz."""
    grupos = _grupo_por_categoria(rules)
    return [{"inicio_ms": m.start_ms, "fim_ms": m.end_ms, "grupo": grupos[m.category]}
           for m in marcas]


# Um fato descritivo por categoria FIAS que de fato ocorreu na aula — nunca uma
# interpretação (isso é MTSS, fora do escopo da W2). Só as categorias 1-9
# aparecem: as observações saem de SEGMENTO classificado, e nenhum segmento
# recebe 10 (classifier.role_categories não a lista para nenhum papel). A
# categoria 10 existe na linha do tempo — é o silêncio que o motor encontra
# entre as falas —, mas não é um segmento de que se possa citar um trecho.
_OBSERVACAO_POR_CATEGORIA = {
    1: "Em algum momento, o professor acolheu o que os estudantes sentiram sobre a aula.",
    2: "O professor elogiou ou incentivou os estudantes.",
    3: "O professor retomou ou usou uma ideia trazida pelos estudantes.",
    4: "O professor fez perguntas aos estudantes.",
    5: "O professor explicou o conteúdo diretamente.",
    6: "O professor deu instruções sobre o que fazer.",
    7: "O professor chamou atenção ou justificou uma regra da aula.",
    8: "Os estudantes responderam a uma pergunta ou instrução do professor.",
    9: "Os estudantes tomaram a iniciativa de falar por conta própria, sem que o professor pedisse.",
}


def _observacoes(linhas: list[tuple[Segmento, ClassificacaoFIAS]]) -> list[dict]:
    # select_evidence_segments (fias_ed_engine.mtss) espera "category" — o
    # docstring dela é explícito: mapear pred_role_constrained para category é
    # responsabilidade de quem chama. segmento_id/trecho viajam junto no mesmo
    # dicionário só para religar a evidência escolhida ao trecho de origem.
    segmentos = [{"category": cls.pred_role_constrained, "confidence": cls.confidence, "start_ms": seg.start_ms,
                 "segmento_id": str(seg.id), "trecho": texto_efetivo(seg)} for seg, cls in linhas]
    categorias_presentes = sorted({s["category"] for s in segmentos})
    return [{
        "texto": _OBSERVACAO_POR_CATEGORIA[cat],
        "evidencias": [{"segmento_id": e["segmento_id"], "inicio_ms": e["start_ms"], "trecho": e["trecho"]}
                      for e in select_evidence_segments(segmentos, cat, limit=3)],
    } for cat in categorias_presentes]


# O que cada índice mede — nunca comparado a um limiar (spec §8.4: os limiares
# do MTSS estão PENDING_SCIENTIFIC_VALIDATION; um veredito ali seria
# inventado). Só os seis índices hoje habilitados em fias_rules.json chegam a
# ter linha em IndicadorFIAS (compute_indices pula os desabilitados); o
# padrão cobre um índice novo que seja habilitado no shared sem acompanhar
# aqui, em vez de um KeyError.
_DESCRICAO_INDICE = {
    "TT": "Proporção do tempo da aula ocupada pela fala do professor, somando as sete categorias docentes do FIAS.",
    "PT": "Proporção do tempo da aula ocupada pela fala dos estudantes, respondendo ou tomando iniciativa.",
    "SC": ("Proporção do tempo da aula em silêncio — trechos de 3 segundos ou mais sem fala. A categoria 10 do FIAS também abriga trechos de confusão, que esta versão não detecta e não conta aqui."),
    "ID_RATIO": ("Razão entre os momentos de influência indireta do professor (acolher, elogiar, usar ideias dos "
                "estudantes, perguntar) e os de influência direta (expor, instruir, criticar)."),
    "PIR": ("Proporção da fala dos estudantes que partiu da iniciativa deles, sem ser resposta a uma pergunta "
           "do professor."),
    "PUPIL_RESPONSE_RATIO": "Proporção da fala dos estudantes que foi resposta a uma pergunta ou instrução do professor.",
}
_DESCRICAO_PADRAO = "Um indicador calculado a partir da distribuição de fala ao longo da aula."


def indices_payload(db: Session, aula_id: uuid.UUID, rules: dict) -> list[dict]:
    nomes = {idx["id"]: idx["name"] for idx in rules["indices"]}
    ordem = {idx["id"]: posicao for posicao, idx in enumerate(rules["indices"])}
    # deleted_at: IndicadorFIAS ganhou exclusão lógica numa task anterior
    # (soft_delete_aula) e esta é a primeira consulta que o lê — sem o filtro,
    # o índice de uma aula excluída reapareceria aqui.
    linhas = db.scalars(select(IndicadorFIAS).where(IndicadorFIAS.aula_id == aula_id,
                                                     IndicadorFIAS.deleted_at.is_(None))).all()
    ordenadas = sorted(linhas, key=lambda r: ordem.get(r.index_id, len(ordem)))
    return [{"codigo": r.index_id, "nome": nomes.get(r.index_id, r.index_id), "valor": r.value,
            "descricao": _DESCRICAO_INDICE.get(r.index_id, _DESCRICAO_PADRAO)} for r in ordenadas]


@router.get("/aulas/{aula_id}/padroes")
def padroes_de_interacao(aula_id: uuid.UUID, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    aula = get_owned_aula(db, actor, aula_id)
    if aula.status not in POS_CLASSIFICACAO:
        raise AppError(409, "AULA_STATE", "Esta aula ainda não tem uma classificação para mostrar.")
    transcricao = transcricao_da_aula(db, aula.id)
    if transcricao is None:
        raise AppError(404, "TRANSCRICAO_NAO_ENCONTRADA", "Esta aula ainda não tem transcrição.")

    regras = load_rules("fias_rules")
    linhas = db.execute(
        select(Segmento, ClassificacaoFIAS)
        .join(ClassificacaoFIAS, ClassificacaoFIAS.segmento_id == Segmento.id)
        .where(Segmento.transcricao_id == transcricao.id)
        .order_by(Segmento.start_ms)
    ).all()
    # codificacao_da_aula (app/fias/service.py): a tela não pode mostrar uma
    # codificação diferente da que produziu os índices que ela exibe ao lado,
    # nem da que a triangulação usa para o mesmo par (professor, aula).
    codificacao = codificacao_da_aula(db, aula, regras)

    audit(db, actor, "aula", aula.id, "read")
    db.commit()
    return {
        "faixa": _faixa(codificacao.marks, regras),
        "observacoes": _observacoes(linhas),
        "matriz": transition_matrix(codificacao.intervals, regras),
        "indices": indices_payload(db, aula.id, regras),
        # Rastreabilidade, não índice: quanto tempo da aula a categoria 10
        # recebeu por silêncio. Não há número de confusão porque confusão não é
        # medida nesta versão (fias_rules.confusion.implemented = false), e um
        # zero em toda aula se leria como "esta aula não teve confusão".
        "tempo_de_silencio_ms": codificacao.silence_ms,
    }
