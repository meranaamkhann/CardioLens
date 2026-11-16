"""health record

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-15 04:13:30.372978
"""
from alembic import op
import sqlalchemy as sa


revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('diagnoses',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('patient_id', sa.Integer(), nullable=False),
    sa.Column('icd10', sa.String(length=10), nullable=False),
    sa.Column('description', sa.String(length=200), nullable=False),
    sa.Column('severity', sa.String(length=10), nullable=True),
    sa.Column('status', sa.String(length=10), nullable=False),
    sa.Column('diagnosed_on', sa.Date(), nullable=True),
    sa.Column('source', sa.String(length=10), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['patient_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('diagnoses', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_diagnoses_patient_id'), ['patient_id'], unique=False)

    op.create_table('diet_plans',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('patient_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('diet_type', sa.String(length=40), nullable=True),
    sa.Column('calories', sa.Integer(), nullable=True),
    sa.Column('protein_g', sa.Float(), nullable=True),
    sa.Column('carbs_g', sa.Float(), nullable=True),
    sa.Column('fat_g', sa.Float(), nullable=True),
    sa.Column('restrictions', sa.JSON(), nullable=False),
    sa.Column('start_date', sa.Date(), nullable=True),
    sa.Column('end_date', sa.Date(), nullable=True),
    sa.Column('notes', sa.String(length=500), nullable=True),
    sa.Column('source', sa.String(length=10), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['patient_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('diet_plans', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_diet_plans_patient_id'), ['patient_id'], unique=False)

    op.create_table('lab_checkups',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('patient_id', sa.Integer(), nullable=False),
    sa.Column('checkup_date', sa.Date(), nullable=False),
    sa.Column('values', sa.JSON(), nullable=False),
    sa.Column('notes_encrypted', sa.Text(), nullable=True),
    sa.Column('source', sa.String(length=10), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['patient_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('lab_checkups', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_lab_checkups_checkup_date'), ['checkup_date'], unique=False)
        batch_op.create_index(batch_op.f('ix_lab_checkups_patient_id'), ['patient_id'], unique=False)

    op.create_table('medications',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('patient_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('dose', sa.String(length=60), nullable=True),
    sa.Column('frequency', sa.String(length=60), nullable=True),
    sa.Column('reason', sa.String(length=120), nullable=True),
    sa.Column('start_date', sa.Date(), nullable=True),
    sa.Column('end_date', sa.Date(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('source', sa.String(length=10), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['patient_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('medications', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_medications_patient_id'), ['patient_id'], unique=False)

    op.create_table('health_alerts',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('patient_id', sa.Integer(), nullable=False),
    sa.Column('severity', sa.String(length=10), nullable=False),
    sa.Column('kind', sa.String(length=10), nullable=False),
    sa.Column('biomarker', sa.String(length=30), nullable=True),
    sa.Column('message', sa.String(length=500), nullable=False),
    sa.Column('checkup_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('acknowledged_by', sa.Integer(), nullable=True),
    sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['acknowledged_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['checkup_id'], ['lab_checkups.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['patient_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('health_alerts', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_health_alerts_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_health_alerts_patient_id'), ['patient_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_health_alerts_severity'), ['severity'], unique=False)


def downgrade():
    with op.batch_alter_table('health_alerts', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_health_alerts_severity'))
        batch_op.drop_index(batch_op.f('ix_health_alerts_patient_id'))
        batch_op.drop_index(batch_op.f('ix_health_alerts_created_at'))

    op.drop_table('health_alerts')
    with op.batch_alter_table('medications', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_medications_patient_id'))

    op.drop_table('medications')
    with op.batch_alter_table('lab_checkups', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_lab_checkups_patient_id'))
        batch_op.drop_index(batch_op.f('ix_lab_checkups_checkup_date'))

    op.drop_table('lab_checkups')
    with op.batch_alter_table('diet_plans', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_diet_plans_patient_id'))

    op.drop_table('diet_plans')
    with op.batch_alter_table('diagnoses', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_diagnoses_patient_id'))

    op.drop_table('diagnoses')
