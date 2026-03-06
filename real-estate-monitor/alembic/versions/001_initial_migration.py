"""Initial migration - create all tables

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create sources table
    op.create_table(
        'sources',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('fetch_mode', sa.String(length=20), nullable=False, server_default='playwright'),
        sa.Column('base_url', sa.String(length=500), nullable=False),
        sa.Column('interval_seconds', sa.Integer(), nullable=False, server_default='60'),
        sa.Column('rate_limit_rps', sa.Numeric(precision=5, scale=2), nullable=False, server_default='1.0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    
    # Create offers table
    op.create_table(
        'offers',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('fingerprint', sa.String(length=64), nullable=False),
        sa.Column('url', sa.String(length=1000), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('price', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('currency', sa.String(length=10), nullable=True),
        sa.Column('city', sa.String(length=100), nullable=True),
        sa.Column('region', sa.String(length=100), nullable=True),
        sa.Column('area_m2', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('rooms', sa.Integer(), nullable=True),
        sa.Column('lat', sa.Numeric(precision=10, scale=6), nullable=True),
        sa.Column('lng', sa.Numeric(precision=10, scale=6), nullable=True),
        sa.Column('raw_json', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('first_seen', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_seen', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['source_id'], ['sources.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('fingerprint', name='uq_offers_fingerprint')
    )
    
    # Create indexes for offers
    op.create_index('ix_offers_last_seen', 'offers', ['last_seen'], unique=False)
    op.create_index('ix_offers_first_seen', 'offers', ['first_seen'], unique=False)
    op.create_index('ix_offers_source_id', 'offers', ['source_id'], unique=False)
    op.create_index('ix_offers_fingerprint', 'offers', ['fingerprint'], unique=False)
    
    # Create notifications table
    op.create_table(
        'notifications',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('offer_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('channel', sa.String(length=50), nullable=False, server_default='whatsapp'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('tries', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['offer_id'], ['offers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for notifications
    op.create_index('ix_notifications_status', 'notifications', ['status'], unique=False)
    op.create_index('ix_notifications_offer_id', 'notifications', ['offer_id'], unique=False)
    
    # Create scrape_runs table
    op.create_table(
        'scrape_runs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='running'),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('offers_found', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('offers_new', sa.Integer(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['source_id'], ['sources.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for scrape_runs
    op.create_index('ix_scrape_runs_started_at', 'scrape_runs', ['started_at'], unique=False)
    op.create_index('ix_scrape_runs_source_id', 'scrape_runs', ['source_id'], unique=False)
    op.create_index('ix_scrape_runs_status', 'scrape_runs', ['status'], unique=False)


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('scrape_runs')
    op.drop_table('notifications')
    op.drop_table('offers')
    op.drop_table('sources')
