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
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.messages import error_message
from app.models import Aula, Ciclo, ColetaQTI, RespostaQTI, ResultadoQTI, utcnow
from app.pipeline.estados import avancar


def _coleta_viva_da_data(db: Session, ciclo: Ciclo, data: dt.date) -> ColetaQTI | None:
    return db.execute(
        select(ColetaQTI).where(ColetaQTI.ciclo_id == ciclo.id,
                                ColetaQTI.coletado_em == data,
                                ColetaQTI.deleted_at.is_(None))
    ).scalars().first()


def _reusar_ou_recusar(existente: ColetaQTI) -> ColetaQTI:
    if existente.origem == "COLETA_NATIVA":
        return existente
    raise AppError(409, "COLETA_JA_EXISTE",
                   "Já existe um relatório importado para esta data. Use outra data, "
                   "ou apague a coleta importada antes de gerar o link.")


def coleta_nativa_do_dia(db: Session, ciclo: Ciclo, data: dt.date) -> ColetaQTI:
    """A coleta nativa daquela data, criada se ainda não existir. Gerar um
    segundo link para o mesmo dia reusa a coleta: duas coletas vivas na mesma
    data fariam a triangulação escolher arbitrariamente qual vale, que é o
    mesmo defeito que a reimportação já evita do outro lado.

    A consulta NÃO filtra por origem — é o que encontra que decide. Se já
    existe uma coleta viva na data e ela é nativa, reusa (mesmo motivo de
    sempre). Se é importada, recusa: gerar um link não traz dado nenhum, e
    apagar uma coleta importada (que tem respostas de verdade) só porque
    alguém clicou em "gerar link" destruiria trabalho por um gesto que não
    pede isso — ao contrário de reimportar, que traz dado novo e substituir
    é razoável. Por isso o sentido inverso (`importar_relatorio`) segue sem
    filtrar por origem: as duas funções olham a mesma linha, cada uma decide
    o que fazer com o que acha.

    A restrição uq_coleta_qti_ciclo_data_viva (migração 0012) é quem decide a
    corrida entre dois pedidos simultâneos; aqui só se relê o que ganhou e se
    aplica a mesma regra."""
    existente = _coleta_viva_da_data(db, ciclo, data)
    if existente is not None:
        return _reusar_ou_recusar(existente)
    cfg = load_rules("qti_config")
    coleta = ColetaQTI(ciclo_id=ciclo.id, coletado_em=data, origem="COLETA_NATIVA",
                       response_count=0, displayable=False,
                       qti_config_version=cfg["rules_version"], cabecalho_recebido=None)
    try:
        with db.begin_nested():
            db.add(coleta)
            db.flush()
    except IntegrityError:
        # Outro pedido criou a coleta desta data entre a consulta e o INSERT.
        return _reusar_ou_recusar(_coleta_viva_da_data(db, ciclo, data))
    return coleta


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
        db.flush()

    agregado = aggregate(respostas, cfg)
    cabecalho = texto.splitlines()[0] if texto else ""
    coleta = ColetaQTI(ciclo_id=ciclo.id, coletado_em=coletado_em, origem="IMPORTACAO_EXTERNA",
                       response_count=agregado["response_count"], displayable=agregado["displayable"],
                       qti_config_version=cfg["rules_version"], cabecalho_recebido=cabecalho)
    try:
        with db.begin_nested():
            db.add(coleta)
            db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise AppError(409, "COLETA_CONCORRENTE", error_message("COLETA_CONCORRENTE")) from exc
    for i, r in enumerate(respostas):
        db.add(RespostaQTI(coleta_id=coleta.id, response_index=i,
                           respostas={str(k): v for k, v in r.items()}))
    db.add(ResultadoQTI(coleta_id=coleta.id, octantes=agregado["octants"],
                        agency=agregado["agency"], communion=agregado["communion"]))
    db.commit()

    # Destrava quem estava parado esperando exatamente este questionário: sem
    # isto WAITING_QTI é beco sem saída, e a primeira aula do ciclo nunca
    # chega ao relatório. Só aulas já paradas em WAITING_QTI — nenhuma outra é
    # tocada, e quem já passou por aqui não é reprocessado.
    presas = db.scalars(select(Aula).where(Aula.turma_id == ciclo.turma_id,
                                            Aula.disciplina_id == ciclo.disciplina_id,
                                            Aula.lesson_date >= ciclo.iniciado_em,
                                            Aula.status == "WAITING_QTI",
                                            Aula.deleted_at.is_(None))).all()
    for presa in presas:
        avancar(db, presa)

    return coleta
