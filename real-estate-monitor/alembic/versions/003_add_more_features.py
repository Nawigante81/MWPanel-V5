"""Add more features tables

Revision ID: 003
Revises: 002
Create Date: 2024-01-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add columns to offers table
    op.add_column('offers', sa.Column('status', sa.String(length=20), server_default='active', nullable=False))
    op.add_column('offers', sa.Column('status_changed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('offers', sa.Column('status_checked_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False))
    op.add_column('offers', sa.Column('search_vector', sa.Text(), nullable=True))
    
    # Create indexes for offers
    op.create_index('ix_offers_status', 'offers', ['status'], unique=False)
    op.create_index('ix_offers_search_vector', 'offers', ['search_vector'], unique=False, postgresql_using='gin')
    
    # Create offer_notes table
    op.create_table(
        'offer_notes',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('offer_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', sa.String(length=100), nullable=False),
        sa.Column('note', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['offer_id'], ['offers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('ix_offer_notes_offer_id', 'offer_notes', ['offer_id'], unique=False)
    op.create_index('ix_offer_notes_user_id', 'offer_notes', ['user_id'], unique=False)
    
    # Create user_favorites table
    op.create_table(
        'user_favorites',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('offer_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['offer_id'], ['offers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('offer_id', 'user_id', name='uq_user_favorite')
    )
    
    op.create_index('ix_user_favorites_offer_id', 'user_favorites', ['offer_id'], unique=False)
    op.create_index('ix_user_favorites_user_id', 'user_favorites', ['user_id'], unique=False)
    
    # Create offer_tags table
    op.create_table(
        'offer_tags',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('offer_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tag', sa.String(length=50), nullable=False),
        sa.Column('created_by', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['offer_id'], ['offers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('offer_id', 'tag', name='uq_offer_tag')
    )
    
    op.create_index('ix_offer_tags_offer_id', 'offer_tags', ['offer_id'], unique=False)
    op.create_index('ix_offer_tags_tag', 'offer_tags', ['tag'], unique=False)
    
    # Create alert_rules table
    op.create_table(
        'alert_rules',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', sa.String(length=100), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('conditions', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('channels', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('cooldown_minutes', sa.Integer(), nullable=False, server_default='60'),
        sa.Column('last_triggered', sa.DateTime(timezone=True), nullable=True),
        sa.Column('trigger_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('ix_alert_rules_user_id', 'alert_rules', ['user_id'], unique=False)
    op.create_index('ix_alert_rules_is_active', 'alert_rules', ['is_active'], unique=False)
    
    # Create weekly_reports table
    op.create_table(
        'weekly_reports',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', sa.String(length=100), nullable=False),
        sa.Column('week_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('week_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('total_new_offers', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_price_drops', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('avg_price', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('top_cities', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('report_data', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('sent_to', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('ix_weekly_reports_user_id', 'weekly_reports', ['user_id'], unique=False)
    op.create_index('ix_weekly_reports_week_start', 'weekly_reports', ['week_start'], unique=False)


def downgrade() -> None:
    # Drop tables
    op.drop_table('weekly_reports')
    op.drop_table('alert_rules')
    op.drop_table('offer_tags')
    op.drop_table('user_favorites')
    op.drop_table('offer_notes')
    
    # Remove columns from offers
    op.drop_index('ix_offers_status', table_name='offers')
    op.drop_index('ix_offers_search_vector', table_name='offers')
    op.drop_column('offers', 'status')
    op.drop_column('offers', 'status_changed_at')
    op.drop_column('offers', 'status_checked_at')
    op.drop_column('offers', 'search_vector')
