"""O link público é a única porta sem autenticação do sistema (§10 da spec).

O segredo vive em dois lugares e só dois: na mão de quem recebeu o link, e
como hash nesta tabela. `criar_link` é a única função que o devolve em claro,
e o chamador tem uma única chance de entregá-lo ao professor — depois disso
nem o banco nem o sistema conseguem reconstruí-lo.
"""
import datetime as dt
import hashlib
import math
import secrets
from datetime import timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import ColetaQTI, LinkQTI

# O professor informa o tamanho da turma; a folga cobre quem entrou depois da
# matrícula e quem responde por outro aparelho. Decisão do pesquisador
# (2026-09-25), não achado da literatura.
LIMITE_FOLGA = 1.10


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def criar_link(db: Session, coleta: ColetaQTI, *, n_estudantes: int, dias: int) -> tuple[LinkQTI, str]:
    agora = dt.datetime.now(timezone.utc)
    # Um link vivo por coleta (índice uq_link_qti_um_vivo_por_coleta, migração 0011).
    # A trava na coleta serializa dois pedidos simultâneos: quem chega depois espera,
    # enxerga o link que o primeiro criou e o revoga — em vez de esbarrar no índice.
    db.execute(select(ColetaQTI.id).where(ColetaQTI.id == coleta.id).with_for_update())
    db.execute(update(LinkQTI)
               .where(LinkQTI.coleta_id == coleta.id,
                      LinkQTI.revogado_em.is_(None),
                      LinkQTI.deleted_at.is_(None))
               .values(revogado_em=agora))
    token = secrets.token_urlsafe(32)
    link = LinkQTI(
        coleta_id=coleta.id,
        token_hash=_hash(token),
        expira_em=agora + dt.timedelta(days=dias),
        # `LIMITE_FOLGA` documenta a intenção (10% de folga), mas o cálculo
        # não passa por ela em ponto flutuante: `n * 1.10` sofre erro de
        # arredondamento binário (50 * 1.10 == 55.00000000000001 em Python),
        # e `math.ceil` desse valor entrega 56 em vez de 55. `n * 11 / 10`
        # evita o problema porque a multiplicação inteira (`n * 11`) é exata
        # e, quando o resultado da divisão por 10 é um inteiro matemático
        # exato (como 550/10 = 55), o IEEE 754 devolve exatamente esse
        # inteiro em ponto flutuante — sem a imprecisão que a multiplicação
        # por 1.10 introduz. Achado da revisão (2026-09-26), confirmado em
        # 12, 30, 50, 90 e 100.
        limite_respostas=math.ceil(n_estudantes * 11 / 10),
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link, token


def link_valido(db: Session, token: str) -> LinkQTI | None:
    """None para token errado, link expirado, revogado, apagado, ou de coleta
    apagada. Um só caminho de saída de propósito: quem chama não deve poder
    distinguir os casos, e quem responde muito menos."""
    agora = dt.datetime.now(timezone.utc)
    return db.execute(
        select(LinkQTI).join(ColetaQTI, ColetaQTI.id == LinkQTI.coleta_id)
        .where(LinkQTI.token_hash == _hash(token),
               LinkQTI.deleted_at.is_(None),
               LinkQTI.revogado_em.is_(None),
               LinkQTI.expira_em > agora,
               ColetaQTI.deleted_at.is_(None))
    ).scalars().first()


def revogar(db: Session, link: LinkQTI) -> None:
    link.revogado_em = dt.datetime.now(timezone.utc)
    db.commit()
