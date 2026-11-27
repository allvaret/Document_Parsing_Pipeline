"""schema base: company, asset, report, summary, keypoint

Baseline equivalente a database/schema.sql. Não importa db.models de propósito:
uma migração antiga não pode mudar quando o modelo mudar.

Revision ID: cd587a8d2a73
Revises: 
Create Date: 2026-11-25 10:10:06.946996
"""
from alembic import op
import sqlalchemy as sa


revision = 'cd587a8d2a73'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('company',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('name_normalized', sa.String(), nullable=False),
    sa.Column('cnpj', sa.String(), nullable=True),
    sa.Column('cvm_code', sa.String(), nullable=True),
    sa.Column('kind', sa.String(), server_default='ACAO', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.CheckConstraint("kind IN ('ACAO', 'FII')", name='ck_company_kind'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('cnpj'),
    sa.UniqueConstraint('cvm_code'),
    sa.UniqueConstraint('name_normalized')
    )
    op.create_table('asset',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('company_id', sa.Integer(), nullable=False),
    sa.Column('ticker', sa.String(), nullable=False),
    sa.CheckConstraint('length(ticker) BETWEEN 5 AND 7', name='ck_asset_ticker_len'),
    sa.ForeignKeyConstraint(['company_id'], ['company.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('ticker')
    )
    op.create_index('ix_asset_company', 'asset', ['company_id'], unique=False)
    op.create_table('report',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('company_id', sa.Integer(), nullable=False),
    sa.Column('report_type', sa.String(), nullable=False),
    sa.Column('period', sa.String(), nullable=False),
    sa.Column('file_name', sa.String(), nullable=False),
    sa.Column('file_hash', sa.String(), nullable=False),
    sa.Column('source_url', sa.String(), nullable=True),
    sa.Column('page_count', sa.Integer(), nullable=False),
    sa.Column('extractor_version', sa.String(), server_default='', nullable=False),
    sa.Column('parsed_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("report_type IN ('ITR', 'DFP', 'EARNINGS_RELEASE', 'FATO_RELEVANTE', 'FORMULARIO_REFERENCIA', 'RELATORIO_ADMINISTRACAO', 'OUTRO')", name='ck_report_type'),
    sa.CheckConstraint('length(file_hash) = 64', name='ck_report_hash_len'),
    sa.CheckConstraint('page_count >= 0', name='ck_report_page_count'),
    sa.ForeignKeyConstraint(['company_id'], ['company.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('company_id', 'report_type', 'period'),
    sa.UniqueConstraint('file_hash')
    )
    op.create_table('keypoint',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('report_id', sa.Integer(), nullable=False),
    sa.Column('metric', sa.String(), nullable=False),
    sa.Column('value_text', sa.String(), nullable=False),
    sa.Column('value_numeric', sa.Float(), nullable=True),
    sa.Column('variation_text', sa.String(), nullable=True),
    sa.Column('period', sa.String(), nullable=True),
    sa.Column('page', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['report_id'], ['report.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_keypoint_report', 'keypoint', ['report_id'], unique=False)
    op.create_table('summary',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('report_id', sa.Integer(), nullable=False),
    sa.Column('method', sa.String(), nullable=False),
    sa.Column('model', sa.String(), nullable=False),
    sa.Column('prompt_version', sa.String(), nullable=False),
    sa.Column('content', sa.String(), nullable=False),
    sa.Column('content_format', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.CheckConstraint("content_format IN ('json', 'markdown')", name='ck_summary_format'),
    sa.CheckConstraint("method IN ('heuristic', 'llm')", name='ck_summary_method'),
    sa.CheckConstraint('length(content) > 0', name='ck_summary_content'),
    sa.ForeignKeyConstraint(['report_id'], ['report.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('report_id', 'method', 'model', 'prompt_version')
    )


def downgrade() -> None:
    op.drop_table('summary')
    op.drop_index('ix_keypoint_report', table_name='keypoint')
    op.drop_table('keypoint')
    op.drop_table('report')
    op.drop_index('ix_asset_company', table_name='asset')
    op.drop_table('asset')
    op.drop_table('company')
