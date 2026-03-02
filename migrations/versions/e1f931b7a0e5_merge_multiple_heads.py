"""merge multiple heads

Revision ID: e1f931b7a0e5
Revises: 0cd76c3aaa61, cf444ed39145
Create Date: 2026-03-02 13:35:15.045425

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e1f931b7a0e5'
down_revision = ('0cd76c3aaa61', 'cf444ed39145')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass