"""um link vivo por coleta

A contagem de respostas é por coleta, o teto é por link, e o FOR UPDATE de
app/publico/routes.py trava a linha do link. Com dois links vivos na mesma coleta,
dois envios por links diferentes travam linhas diferentes, leem a mesma contagem e
gravam os dois: o limite estoura e o response_index se repete. Achado da verificação
final da W3b; decisão do pesquisador (2026-09-26): corrigir, não só documentar.

Esta migração torna o estado impossível no banco: no máximo um link não revogado e
não apagado por coleta. Links já expirados contam — criar_link revoga todos os não
revogados da coleta antes de criar o novo, então o índice e o código concordam.

Dado existente. Antes de criar o índice, os links excedentes são REVOGADOS (não
apagados): em cada coleta fica vivo só o mais recente (created_at, depois id). No
banco de desenvolvimento, em 2026-09-26, eram 2 coletas com 2 links vivos cada,
restos da verificação da W3b:

    SELECT count(*), sum(n - 1) FROM (
      SELECT coleta_id, count(*) n FROM link_qti
      WHERE revogado_em IS NULL AND deleted_at IS NULL
      GROUP BY 1 HAVING count(*) > 1) x;
    -- 2 | 2

Revogar é o que a regra nova faria com eles de qualquer jeito, no próximo link
gerado; aqui só acontece antes.

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-26
"""
import sqlalchemy as sa
from alembic import op

revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    revogados = op.get_bind().execute(sa.text("""
        UPDATE link_qti SET revogado_em = now(), updated_at = now()
        WHERE revogado_em IS NULL AND deleted_at IS NULL
          AND id NOT IN (
            SELECT DISTINCT ON (coleta_id) id FROM link_qti
            WHERE revogado_em IS NULL AND deleted_at IS NULL
            ORDER BY coleta_id, created_at DESC, id DESC)
    """)).rowcount
    print(f"0011: {revogados} link(s) excedente(s) revogado(s)")
    op.create_index("uq_link_qti_um_vivo_por_coleta", "link_qti", ["coleta_id"], unique=True,
                    postgresql_where=sa.text("revogado_em IS NULL AND deleted_at IS NULL"))


def downgrade() -> None:
    op.drop_index("uq_link_qti_um_vivo_por_coleta", table_name="link_qti")
