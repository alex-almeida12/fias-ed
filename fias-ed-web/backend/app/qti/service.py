"""Importa o relatório exportado pelo avalie-seu-professor.

Nenhuma regra científica aqui: parse_export_csv valida e recalcula, aggregate
pontua. Este módulo só persiste o que o motor devolveu.

Sobre a versão do formato (decisão registrada aqui, não só no relatório da
tarefa). O plano original desta fatia previa recusar um arquivo que não
declarasse a própria versão. Fui conferir no avalie-seu-professor
(`src/application/use-cases/exportTeacherDataset.ts` e
`src/infrastructure/export/datasetFormats.ts`) e ele não declara versão
nenhuma hoje — nem linha de comentário antes do cabeçalho, nem coluna
dedicada, nem campo de metadado no JSON/XLSX. Esse sistema é do pesquisador,
é separado deste monorepo e as regras da fatia proíbem alterá-lo. Inventar
aqui, do lado do FIAS-ED, um formato de versão que o avalie-seu-professor não
produz faria a importação recusar TODOS os arquivos reais — pior do que não
verificar nada. Decisão: a exigência de versão declarada sai desta fatia.

O que fica no lugar, e é o máximo honesto disponível sem alterar o sistema de
origem: cada ColetaQTI grava `cabecalho_recebido` (a linha de cabeçalho exata
do arquivo importado) e `qti_config_version` (a versão das regras de
pontuação usadas para calcular esta coleta). Isso não impede uma mudança
silenciosa no avalie-seu-professor, mas torna duas coletas nascidas de
formatos de exportação diferentes DISTINGUÍVEIS depois — quem olhar duas
coletas do mesmo ciclo com cabeçalhos diferentes sabe que algo mudou na
origem, mesmo que a importação de nenhuma delas tenha sido recusada.

O que isso NÃO pega, e precisa ficar escrito: se o avalie-seu-professor um
dia reordenar os itens do questionário mantendo os nomes de coluna
q1..q24, nada aqui percebe. Os valores continuam dentro da escala 1..5, as
colunas continuam presentes com os mesmos nomes, e o mapeamento para os
octantes sai silenciosamente errado — o cabeçalho gravado seria idêntico ao
anterior, porque os NOMES das colunas não mudaram, só a ordem em que os itens
foram atribuídos a elas antes da exportação (isso acontece do lado de lá,
antes do CSV existir; não há como este módulo, que só vê o CSV já pronto,
detectar essa reordenação). As defesas que continuam de pé, feitas pelo
motor: parse_export_csv recusa coluna faltando, valor fora da escala 1..5, e
valor que diverge do recálculo a partir das respostas brutas.
"""
import datetime as dt

from fias_ed_engine.qti import QtiImportError, aggregate, parse_export_csv
from fias_ed_engine.rules import load_rules
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.messages import error_message
from app.models import Ciclo, ColetaQTI, RespostaQTI, ResultadoQTI, utcnow


def importar_relatorio(db: Session, ciclo: Ciclo, texto: str, coletado_em: dt.date) -> ColetaQTI:
    cfg = load_rules("qti_config")
    try:
        respostas = parse_export_csv(texto, cfg)
    except QtiImportError as exc:
        raise AppError(422, "QTI_IMPORT_INVALIDO", str(exc)) from exc
    if not respostas:
        raise AppError(422, "QTI_SEM_RESPOSTAS", error_message("QTI_SEM_RESPOSTAS"))

    # Reimportar na mesma data substitui: duas coletas na mesma data deixariam a
    # triangulação escolher arbitrariamente qual é "a mais recente", e o resultado
    # mudaria entre execuções sem ninguém perceber.
    anterior = db.execute(select(ColetaQTI).where(
        ColetaQTI.ciclo_id == ciclo.id, ColetaQTI.coletado_em == coletado_em,
        ColetaQTI.deleted_at.is_(None))).scalars().first()
    if anterior is not None:
        anterior.deleted_at = utcnow()

    agregado = aggregate(respostas, cfg)
    cabecalho = texto.splitlines()[0] if texto else ""
    coleta = ColetaQTI(ciclo_id=ciclo.id, coletado_em=coletado_em, origem="IMPORTACAO_EXTERNA",
                       response_count=agregado["response_count"], displayable=agregado["displayable"],
                       qti_config_version=cfg["rules_version"], cabecalho_recebido=cabecalho)
    db.add(coleta)
    db.flush()
    for i, r in enumerate(respostas):
        db.add(RespostaQTI(coleta_id=coleta.id, response_index=i,
                           respostas={str(k): v for k, v in r.items()}))
    db.add(ResultadoQTI(coleta_id=coleta.id, octantes=agregado["octants"],
                        agency=agregado["agency"], communion=agregado["communion"]))
    db.commit()
    return coleta
