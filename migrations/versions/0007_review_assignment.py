"""Explicit reviewer assignment by the human operator."""
from alembic import op
import sqlalchemy as sa

revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("task", sa.Column("review_assigned_to", sa.String(), nullable=True))


def downgrade():
    op.drop_column("task", "review_assigned_to")
