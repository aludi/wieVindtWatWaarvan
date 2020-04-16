"""add type for date

Revision ID: c0f739474b30
Revises: 78145fe6e3c7
Create Date: 2020-04-14 09:59:39.426166

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c0f739474b30'
down_revision = '78145fe6e3c7'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_index(op.f('ix_sents_date'), 'sents', ['date'], unique=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_sents_date'), table_name='sents')
    # ### end Alembic commands ###
