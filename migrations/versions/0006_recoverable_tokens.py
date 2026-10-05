"""Admin-only encrypted storage for repeatable agent token copy."""
from alembic import op
import sqlalchemy as sa

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("token", sa.Column("token_ciphertext", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("token", "token_ciphertext")
