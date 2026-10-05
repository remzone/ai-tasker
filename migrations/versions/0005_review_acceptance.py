"""AI review and human acceptance, preserving original identifiers."""
from alembic import op
import sqlalchemy as sa

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE taskstatus ADD VALUE IF NOT EXISTS 'acceptance'")
    op.add_column("task", sa.Column("acceptance_criteria", sa.Text(), nullable=False, server_default=""))
    op.add_column("task", sa.Column("work_summary", sa.Text(), nullable=False, server_default=""))
    op.add_column("task", sa.Column("reviewer", sa.String(), nullable=True))


def downgrade():
    op.execute("UPDATE task SET status = 'review' WHERE status = 'acceptance'")
    op.drop_column("task", "reviewer")
    op.drop_column("task", "work_summary")
    op.drop_column("task", "acceptance_criteria")
    # PostgreSQL enum values cannot be dropped without replacing the type.
