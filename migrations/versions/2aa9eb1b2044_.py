"""empty message

Revision ID: 2aa9eb1b2044
Revises: 8a2ccda51ebb
Create Date: 2020-04-10 17:35:18.924809

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2aa9eb1b2044'
down_revision = '8a2ccda51ebb'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('words',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('corpus_words_raw', sa.String(length=200), nullable=True),
    sa.Column('topic_words_raw', sa.String(length=200), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('post',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('book', sa.String(length=200), nullable=True),
    sa.Column('rating', sa.String(length=5), nullable=True),
    sa.Column('color', sa.String(length=20), nullable=True),
    sa.Column('timestamp', sa.DateTime(), nullable=True),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_post_timestamp'), 'post', ['timestamp'], unique=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_post_timestamp'), table_name='post')
    op.drop_table('post')
    op.drop_table('words')
    # ### end Alembic commands ###
