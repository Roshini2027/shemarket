"""fix doc_type enum values to match DocType model

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-06-15 00:00:00.000000
"""
from alembic import op

revision     = 'c3d4e5f6a7b8'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on    = None


def upgrade():
    # Update doc_type ENUM from old values to new values that match DocType model.
    # Old: 'business_registration', 'tax_certificate', 'id_document', 'other'
    # New: 'government_id', 'ownership_proof', 'business_registration'
    #
    # Step 1: Widen the ENUM to include both old and new values so no
    #         existing rows are invalidated during the transition.
    op.execute(
        "ALTER TABLE verification_documents MODIFY COLUMN doc_type "
        "ENUM('business_registration','tax_certificate','id_document','other',"
        "'government_id','ownership_proof') NOT NULL"
    )

    # Step 2: Migrate any existing rows from old values to their closest
    #         new equivalents so no data is lost.
    op.execute(
        "UPDATE verification_documents SET doc_type = 'government_id' "
        "WHERE doc_type = 'id_document'"
    )
    op.execute(
        "UPDATE verification_documents SET doc_type = 'ownership_proof' "
        "WHERE doc_type = 'tax_certificate'"
    )
    op.execute(
        "UPDATE verification_documents SET doc_type = 'business_registration' "
        "WHERE doc_type = 'other'"
    )

    # Step 3: Now that all rows use only the new values, narrow the ENUM
    #         to exactly what the DocType model defines.
    op.execute(
        "ALTER TABLE verification_documents MODIFY COLUMN doc_type "
        "ENUM('government_id','ownership_proof','business_registration') NOT NULL"
    )


def downgrade():
    # Reverse: widen first, migrate back, then narrow to old values.
    op.execute(
        "ALTER TABLE verification_documents MODIFY COLUMN doc_type "
        "ENUM('business_registration','tax_certificate','id_document','other',"
        "'government_id','ownership_proof') NOT NULL"
    )
    op.execute(
        "UPDATE verification_documents SET doc_type = 'id_document' "
        "WHERE doc_type = 'government_id'"
    )
    op.execute(
        "UPDATE verification_documents SET doc_type = 'tax_certificate' "
        "WHERE doc_type = 'ownership_proof'"
    )
    op.execute(
        "ALTER TABLE verification_documents MODIFY COLUMN doc_type "
        "ENUM('business_registration','tax_certificate','id_document','other') NOT NULL"
    )
