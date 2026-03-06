"""Add source_created_at and imported_at to offers

Revision ID: 004
Revises: 003
Create Date: 2026-03-05 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('offers', sa.Column('source_created_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('offers', sa.Column('imported_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True))

    # Backfill existing rows
    op.execute("""
        UPDATE offers
        SET source_created_at = COALESCE(source_created_at, first_seen),
            imported_at = COALESCE(imported_at, first_seen)
    """)

    # Enforce NOT NULL for imported_at after backfill
    op.alter_column('offers', 'imported_at', nullable=False)

    op.create_index('ix_offers_source_created_at', 'offers', ['source_created_at'], unique=False)
    op.create_index('ix_offers_imported_at', 'offers', ['imported_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_offers_imported_at', table_name='offers')
    op.drop_index('ix_offers_source_created_at', table_name='offers')
    op.drop_column('offers', 'imported_at')
    op.drop_column('offers', 'source_created_at')
