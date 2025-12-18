"""

Revision ID: cf444ed39145
Revises: a5d20209ade0
Create Date: 2025-12-18

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "cf444ed39145"
down_revision = "a5d20209ade0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bot_folders",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column(
            "user_manager_id",
            sa.Integer(),
            sa.ForeignKey("user_managers.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_bot_folders_user_manager_id",
        "bot_folders",
        ["user_manager_id"],
    )

    op.add_column("bots", sa.Column("folder_id", sa.Integer(), nullable=True))
    op.create_index("ix_bots_folder_id", "bots", ["folder_id"])
    op.create_foreign_key(
        "fk_bots_folder_id_bot_folders",
        "bots",
        "bot_folders",
        ["folder_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_bots_folder_id_bot_folders", "bots", type_="foreignkey")
    op.drop_index("ix_bots_folder_id", table_name="bots")
    op.drop_column("bots", "folder_id")

    op.drop_index("ix_bot_folders_user_manager_id", table_name="bot_folders")
    op.drop_table("bot_folders")

