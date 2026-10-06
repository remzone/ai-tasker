"""Encrypted OpenRouter drafting settings."""

from alembic import op
import sqlalchemy as sa

revision = "a7b8c9d0e1f2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "openroutersettings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("api_key_ciphertext", sa.String(), nullable=False),
        sa.Column("management_key_ciphertext", sa.String(), nullable=False),
    )


def downgrade():
    op.drop_table("openroutersettings")
