"""Project and task instructions for external agents."""
from alembic import op
import sqlalchemy as sa

revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade():
    for table in ("project", "task"):
        op.add_column(table, sa.Column("agent_instructions", sa.Text(), nullable=False, server_default=""))


def downgrade():
    for table in ("task", "project"):
        op.drop_column(table, "agent_instructions")
