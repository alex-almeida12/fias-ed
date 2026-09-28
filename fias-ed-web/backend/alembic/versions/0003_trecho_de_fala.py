"""linha do tempo de fala do separador de vozes

A evidência de fala/não-fala precisava sobreviver ao fim da diarização: a
classificação FIAS roda depois da revisão de vozes, quando a cópia de trabalho
do áudio já foi apagada, e sem ela o motor mediria silêncio pelas lacunas entre
segmentos do ASR — que o vad_filter do Whisper fecha.

Guarda quando houve fala e quantas vozes ao mesmo tempo, nunca quais: o §48
proíbe agrupamento de voz por estudante em qualquer lugar, inclusive no banco.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-23
"""
from alembic import op
import sqlalchemy as sa

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('trecho_de_fala',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('transcricao_id', sa.UUID(), nullable=False),
    sa.Column('inicio_ms', sa.Integer(), nullable=False),
    sa.Column('fim_ms', sa.Integer(), nullable=False),
    sa.Column('n_vozes', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['transcricao_id'], ['transcricao.id'],
                            name=op.f('fk_trecho_de_fala_transcricao_id_transcricao')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_trecho_de_fala'))
    )
    op.create_index(op.f('ix_trecho_de_fala_transcricao_id'), 'trecho_de_fala',
                    ['transcricao_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_trecho_de_fala_transcricao_id'), table_name='trecho_de_fala')
    op.drop_table('trecho_de_fala')
