"""resultado_qti unico por coleta

Uma coleta tem UM resultado agregado — invariante de domínio, não só cuidado
de concorrência. Até aqui `resultado_qti.coleta_id` só tinha um índice
simples (`ix_resultado_qti_coleta_id`), sem nada no banco impedindo duas
linhas para a mesma coleta. Isso deixava aberta uma corrida real em
`app/publico/routes.py` (Task 4, W3b): duas respostas chegando por links
diferentes da mesma coleta — o limite de respostas é travado por link, não
por coleta — podiam fazer busca-ou-cria em paralelo no `ResultadoQTI`, as
duas encontrarem vazio, as duas inserirem. Um relatório que encontrasse dois
resultados agregados da mesma coleta escolheria arbitrariamente qual
mostrar, e os números mudariam entre execuções — pior do que furar o limite
de respostas, porque corrompe silenciosamente o dado já mostrado ao
professor.

A tabela `resultado_qti` é de outra fatia (W2/W3a), mas a migração é aditiva
(troca um índice comum por um índice único no mesmo campo) e a invariante
("um resultado por coleta") é inequívoca no domínio, não uma opção de
implementação. Verificado antes de escrever esta migração, contra o banco de
desenvolvimento em execução (`fias-ed-web-db-1`, banco `fias_ed_web`):

    SELECT coleta_id, count(*) FROM resultado_qti
    GROUP BY coleta_id HAVING count(*) > 1;
    -- (0 rows)

Nenhuma linha existente viola a restrição. Se uma instalação em campo
tiver dado que viole, `op.create_unique_constraint` abaixo falha a
migração (não apaga nada) — é o comportamento correto: um dado assim exige
decisão humana sobre qual das duas linhas é a válida, não uma escolha
automática de migração.

Travada por teste que insere duas linhas de `ResultadoQTI` para a mesma
coleta e espera `IntegrityError`
(test_qti_modelo.py::test_resultado_qti_recusa_duas_linhas_para_a_mesma_coleta).

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-26
"""
from alembic import op

revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index(op.f('ix_resultado_qti_coleta_id'), table_name='resultado_qti')
    op.create_unique_constraint(op.f('uq_resultado_qti_coleta_id'), 'resultado_qti', ['coleta_id'])


def downgrade() -> None:
    op.drop_constraint(op.f('uq_resultado_qti_coleta_id'), 'resultado_qti', type_='unique')
    op.create_index(op.f('ix_resultado_qti_coleta_id'), 'resultado_qti', ['coleta_id'], unique=False)
