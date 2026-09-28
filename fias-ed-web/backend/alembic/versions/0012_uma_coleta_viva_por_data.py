"""uma coleta viva por acompanhamento e data

coleta_nativa_do_dia reusa a coleta viva da data, e importar_relatorio apaga
logicamente a anterior antes de criar a nova: as duas funções já mantêm, no código,
"no máximo uma coleta viva por (ciclo, data)". Faltava o banco. Sem ele, dois
pedidos simultâneos — dois cliques em "gerar link", ou duas importações — passam os
dois pela consulta, não acham nada e criam duas coletas vivas; a triangulação passa a
escolher entre elas pelo desempate, e o professor vê números de uma coleta que não é
a que ele acabou de enviar.

Parcial (WHERE deleted_at IS NULL) de propósito: a reimportação cria uma coleta nova
na mesma data de uma que ela acabou de apagar logicamente.

Dado existente, conferido no banco de desenvolvimento em 2026-09-26: 14 coletas
vivas, nenhuma violação. Se uma instalação tiver violação, esta migração PARA com a
contagem, sem apagar nada: qual das coletas vale é decisão humana.

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-26
"""
import sqlalchemy as sa
from alembic import op

revision = '0012'
down_revision = '0011'
branch_labels = None
depends_on = None


def upgrade() -> None:
    duplicadas = op.get_bind().execute(sa.text("""
        SELECT count(*) FROM (
          SELECT ciclo_id, coletado_em FROM coleta_qti WHERE deleted_at IS NULL
          GROUP BY 1, 2 HAVING count(*) > 1) d
    """)).scalar_one()
    if duplicadas:
        raise RuntimeError(
            f"{duplicadas} par(es) (acompanhamento, data) com mais de uma coleta viva. "
            "Decida à mão qual vale antes de migrar; esta migração não apaga nada.")
    op.create_index("uq_coleta_qti_ciclo_data_viva", "coleta_qti", ["ciclo_id", "coletado_em"],
                    unique=True, postgresql_where=sa.text("deleted_at IS NULL"))


def downgrade() -> None:
    op.drop_index("uq_coleta_qti_ciclo_data_viva", table_name="coleta_qti")
