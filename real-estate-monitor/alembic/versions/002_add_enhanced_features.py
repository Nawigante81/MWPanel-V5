"""Add enhanced features tables

Revision ID: 002
Revises: 001
Create Date: 2024-01-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create price_history table
    op.create_table(
        'price_history',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('offer_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('price', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('currency', sa.String(length=10), nullable=False, server_default='PLN'),
        sa.Column('recorded_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('price_change_percent', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['offer_id'], ['offers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('ix_price_history_offer_id', 'price_history', ['offer_id'], unique=False)
    op.create_index('ix_price_history_recorded_at', 'price_history', ['recorded_at'], unique=False)
    
    # Create webhooks table
    op.create_table(
        'webhooks',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('url', sa.String(length=1000), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=True),
        sa.Column('secret', sa.String(length=500), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('filters', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_triggered', sa.DateTime(timezone=True), nullable=True),
        sa.Column('fail_count', sa.Integer(), nullable=False, server_default='0'),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('ix_webhooks_is_active', 'webhooks', ['is_active'], unique=False)
    
    # Create user_preferences table
    op.create_table(
        'user_preferences',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', sa.String(length=100), nullable=False),
        sa.Column('preferred_cities', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('preferred_regions', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('max_distance_km', sa.Float(), nullable=True),
        sa.Column('reference_lat', sa.Numeric(precision=10, scale=6), nullable=True),
        sa.Column('reference_lng', sa.Numeric(precision=10, scale=6), nullable=True),
        sa.Column('min_price', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('max_price', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('min_area', sa.Float(), nullable=True),
        sa.Column('max_area', sa.Float(), nullable=True),
        sa.Column('preferred_rooms', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('price_weight', sa.Float(), nullable=False, server_default='0.3'),
        sa.Column('location_weight', sa.Float(), nullable=False, server_default='0.3'),
        sa.Column('size_weight', sa.Float(), nullable=False, server_default='0.2'),
        sa.Column('rooms_weight', sa.Float(), nullable=False, server_default='0.2'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )
    
    # Create image_analysis table
    op.create_table(
        'image_analysis',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('offer_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('image_url', sa.String(length=1000), nullable=False),
        sa.Column('room_count_estimate', sa.Integer(), nullable=True),
        sa.Column('has_furniture', sa.Boolean(), nullable=True),
        sa.Column('condition_score', sa.Float(), nullable=True),
        sa.Column('brightness_score', sa.Float(), nullable=True),
        sa.Column('perceptual_hash', sa.String(length=64), nullable=True),
        sa.Column('analyzed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['offer_id'], ['offers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('ix_image_analysis_offer_id', 'image_analysis', ['offer_id'], unique=False)
    op.create_index('ix_image_analysis_perceptual_hash', 'image_analysis', ['perceptual_hash'], unique=False)
    
    # Create failed_scrapes table
    op.create_table(
        'failed_scrapes',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source_name', sa.String(length=100), nullable=False),
        sa.Column('filter_config', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('error', sa.Text(), nullable=False),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_retries', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('next_retry_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('ix_failed_scrapes_source_name', 'failed_scrapes', ['source_name'], unique=False)
    op.create_index('ix_failed_scrapes_status', 'failed_scrapes', ['status'], unique=False)
    op.create_index('ix_failed_scrapes_next_retry_at', 'failed_scrapes', ['next_retry_at'], unique=False)
    
    # Update notifications table - add new columns
    op.add_column('notifications', sa.Column('recipient', sa.String(length=500), nullable=True))
    op.add_column('notifications', sa.Column('max_retries', sa.Integer(), server_default='8', nullable=False))
    op.add_column('notifications', sa.Column('response_data', postgresql.JSON(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    # Drop new tables
    op.drop_table('failed_scrapes')
    op.drop_table('image_analysis')
    op.drop_table('user_preferences')
    op.drop_table('webhooks')
    op.drop_table('price_history')
    
    # Remove columns from notifications
    op.drop_column('notifications', 'recipient')
    op.drop_column('notifications', 'max_retries')
    op.drop_column('notifications', 'response_data')
