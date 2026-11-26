"""add resumes

One uploaded resume (PDF or Word) per user, stored as raw bytes for the agent to parse later.
Row-level security on with no policies, like every other table: only the backend can read it.

Revision ID: d5eed602ff4f
Revises: 20d6ad470b95
Create Date: 2026-11-25 21:56:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd5eed602ff4f'
down_revision: Union[str, Sequence[str], None] = '20d6ad470b95'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('resumes',
    sa.Column('user_id', postgresql.UUID(as_uuid=False), nullable=False),
    sa.Column('filename', sa.Text(), nullable=False),
    sa.Column('content_type', sa.Text(), nullable=False),
    sa.Column('size', sa.Integer(), nullable=False),
    sa.Column('data', sa.LargeBinary(), nullable=False),
    sa.Column('uploaded_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['profiles.user_id'], name=op.f('fk_resumes_user_id_profiles'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', name=op.f('pk_resumes'))
    )
    op.execute('ALTER TABLE resumes ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('resumes')
