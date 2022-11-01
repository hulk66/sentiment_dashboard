"""Rename Table

Revision ID: cd119aedda0f
Revises: 3ce4d16587b7
Create Date: 2022-11-01 16:26:26.984422

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'cd119aedda0f'
down_revision = '3ce4d16587b7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.rename_table("recommendation", "fin_data")


def downgrade() -> None:
    op.rename_table("fin_data", "recommendation")
