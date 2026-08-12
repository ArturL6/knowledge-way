"""add versioned retrieval documents

Revision ID: 20260812_0012
Revises: 20260812_0011
"""
from alembic import op
import sqlalchemy as sa
revision='20260812_0012'
down_revision='20260812_0011'
branch_labels=None
depends_on=None

def upgrade():
 op.create_table('retrieval_documents',sa.Column('id',sa.String(36),primary_key=True),sa.Column('kind',sa.String(20),nullable=False),sa.Column('subject_id',sa.String(512),nullable=False),sa.Column('parent_id',sa.String(512)),sa.Column('repository_id',sa.String(36),sa.ForeignKey('repositories.id',ondelete='CASCADE'),nullable=False),sa.Column('indexed_commit_sha',sa.String(64),nullable=False),sa.Column('source_fingerprint',sa.String(64),nullable=False),sa.Column('provenance_fingerprint',sa.String(64),nullable=False),sa.Column('content_hash',sa.String(64),nullable=False),sa.Column('schema_version',sa.String(64),nullable=False),sa.Column('content',sa.Text(),nullable=False),sa.Column('created_at',sa.DateTime(),nullable=False),sa.UniqueConstraint('kind','subject_id','parent_id','repository_id','indexed_commit_sha','source_fingerprint','provenance_fingerprint','content_hash',name='uq_retrieval_documents_version'))
 for name,columns in [('ix_retrieval_documents_repo_kind',['repository_id','kind']),('ix_retrieval_documents_kind',['kind']),('ix_retrieval_documents_subject_id',['subject_id']),('ix_retrieval_documents_parent_id',['parent_id']),('ix_retrieval_documents_repository_id',['repository_id']),('ix_retrieval_documents_indexed_commit_sha',['indexed_commit_sha']),('ix_retrieval_documents_source_fingerprint',['source_fingerprint']),('ix_retrieval_documents_provenance_fingerprint',['provenance_fingerprint']),('ix_retrieval_documents_content_hash',['content_hash'])]: op.create_index(name,'retrieval_documents',columns)
def downgrade(): op.drop_table('retrieval_documents')
