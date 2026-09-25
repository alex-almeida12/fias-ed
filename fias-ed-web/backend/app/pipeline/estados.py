"""Depois de `FIAS_COMPLETED`, a aula ainda precisa da triangulação com o QTI e
da interpretação MTSS antes do relatório estar pronto. `avancar` é a única
função que sabe essa ordem — orquestra `ciclos`, `triangulacao` e `mtss`, três
módulos que não podem depender um do outro sem criar ciclo de importação ou
enterrar a regra do calendário dentro do módulo errado.

Cada estado é marcado pelo passo que o alcança, nunca por antecipação: se
`TRIANGULATED` fosse gravado antes de `triangular` rodar, a tela mentiria para
quem está olhando enquanto o trabalho ainda está em andamento.

Só a primeira e a última aula do ciclo esperam o questionário — é isso que
permite mostrar trajetória entre as duas pontas. Aula fora de ciclo e aula do
meio seguem direto: travar o meio seguraria o relatório de uma aula por causa
de um questionário que ainda não precisa existir.
"""
from sqlalchemy.orm import Session

from app.ciclos.service import posicao_no_ciclo
from app.models import Aula
from app.mtss.service import interpretar
from app.triangulacao.service import coleta_vigente, triangular

_PONTAS_DO_CICLO = ("primeira", "ultima", "primeira_e_ultima")


def avancar(db: Session, aula: Aula) -> None:
    posicao = posicao_no_ciclo(db, aula)
    if posicao in _PONTAS_DO_CICLO and coleta_vigente(db, aula) is None:
        aula.status, aula.error_code = "WAITING_QTI", None
        db.commit()
        return

    triangular(db, aula)
    aula.status, aula.error_code = "TRIANGULATED", None
    db.commit()

    interpretar(db, aula)
    aula.status, aula.error_code = "MTSS_INTERPRETED", None
    db.commit()

    aula.status, aula.error_code = "REPORT_READY", None
    db.commit()
