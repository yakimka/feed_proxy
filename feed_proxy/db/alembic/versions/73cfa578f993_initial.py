"""Initial

Revision ID: 73cfa578f993
Revises: 
Create Date: 2020-12-06 18:11:08.948322

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '73cfa578f993'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('feed_proxy_processed',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('source_name', sa.String(), nullable=False),
    sa.Column('post_id', sa.String(), nullable=False),
    sa.Column('created', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk__feed_proxy_processed')),
    sa.UniqueConstraint('source_name', 'post_id', name=op.f('uq__feed_proxy_processed__source_name_post_id'))
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('feed_proxy_processed')
    # ### end Alembic commands ###