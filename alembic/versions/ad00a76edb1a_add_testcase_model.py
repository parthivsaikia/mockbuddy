"""Add TestCase model

Revision ID: ad00a76edb1a
Revises: 53540199fd76
Create Date: 2025-06-07 07:53:40.915852

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ad00a76edb1a'
down_revision: Union[str, None] = '53540199fd76'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.create_table(
        'test_cases',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('company', sa.String(), nullable=True),
        sa.Column('question_hash', sa.String(), nullable=False, unique=True),
        sa.Column('problem_statement', sa.Text(), nullable=False),
        sa.Column('input_data', sa.Text(), nullable=False),
        sa.Column('expected_output', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )


def downgrade():
    op.drop_table('test_cases')