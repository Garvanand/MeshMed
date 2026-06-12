"""
MeshMed SQLAlchemy Models.

Defines the PostgreSQL schema for storing unified medical timelines.
Note: All PHI fields are stored as Text to accommodate Fernet base64 encrypted strings.
"""

from datetime import date
from typing import Optional
import uuid

from sqlalchemy import Column, Date, Enum, ForeignKey, String, Text, Integer, DateTime, func
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from meshmed.models.schemas import DocumentType, MedicationStatus

Base = declarative_base()

class Patient(Base):
    __tablename__ = "patients"
    __table_args__ = {"schema": "meshmed"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    abha_id = Column(String, index=True, nullable=True)  # ABHA ID is standard, non-PHI identifier
    
    # --- PHI FIELDS (Must be encrypted before insert) ---
    name_encrypted = Column(Text, nullable=False)
    phone_number_encrypted = Column(Text, nullable=False)
    dob_encrypted = Column(Text, nullable=True)
    # ----------------------------------------------------
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    documents = relationship("MedicalDocument", back_populates="patient", cascade="all, delete-orphan")
    medications = relationship("Medication", back_populates="patient", cascade="all, delete-orphan")


class MedicalDocument(Base):
    __tablename__ = "medical_documents"
    __table_args__ = {"schema": "meshmed"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("meshmed.patients.id"), nullable=False)
    
    doc_type = Column(Enum(DocumentType), nullable=False)
    date_of_service = Column(Date, nullable=True)
    
    # --- PHI FIELDS (Must be encrypted before insert) ---
    provider_name_encrypted = Column(Text, nullable=True)
    raw_text_encrypted = Column(Text, nullable=False)        # Raw OCR/PDF text
    structured_data_encrypted = Column(JSONB, nullable=True) # The JSON output from LLM
    # ----------------------------------------------------
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    patient = relationship("Patient", back_populates="documents")


class Medication(Base):
    __tablename__ = "medications"
    __table_args__ = {"schema": "meshmed"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("meshmed.patients.id"), nullable=False)
    source_document_id = Column(UUID(as_uuid=True), ForeignKey("meshmed.medical_documents.id"), nullable=True)
    
    drug_name_normalized = Column(String, nullable=False, index=True) # Safe to index (e.g. "Metformin")
    status = Column(Enum(MedicationStatus), default=MedicationStatus.ACTIVE)
    
    # --- PHI FIELDS (Must be encrypted before insert) ---
    dosage_encrypted = Column(Text, nullable=True)
    instructions_encrypted = Column(Text, nullable=True)
    # ----------------------------------------------------
    
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    
    patient = relationship("Patient", back_populates="medications")
