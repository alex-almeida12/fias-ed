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

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ColetaQTI, LinkQTI

# O professor informa o tamanho da turma; a folga cobre quem entrou depois da
# matrícula e quem responde por outro aparelho. Decisão do pesquisador
# (2026-09-25), não achado da literatura.
LIMITE_FOLGA = 1.10


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def criar_link(db: Session, coleta: ColetaQTI, *, n_estudantes: int, dias: int) -> tuple[LinkQTI, str]:
    token = secrets.token_urlsafe(32)
    link = LinkQTI(
        coleta_id=coleta.id,
        token_hash=_hash(token),
        expira_em=dt.datetime.now(timezone.utc) + dt.timedelta(days=dias),
        limite_respostas=math.ceil(n_estudantes * LIMITE_FOLGA),
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
