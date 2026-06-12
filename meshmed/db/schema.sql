-- MeshMed PostgreSQL Schema definition
-- Database: agentos_shared
-- Schema: meshmed

CREATE SCHEMA IF NOT EXISTS meshmed;

-- =================================================================================
-- USERS TABLE
-- =================================================================================
CREATE TABLE meshmed.users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    abha_id VARCHAR(50) UNIQUE,              -- Ayushman Bharat Health Account ID
    name_encrypted TEXT NOT NULL,            -- PHI: Fernet encrypted
    phone_number_encrypted TEXT NOT NULL,    -- PII: Fernet encrypted
    dob_encrypted TEXT,                      -- PHI: Fernet encrypted
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- =================================================================================
-- MEDICAL DOCUMENTS (Base table for unstructured/raw context)
-- =================================================================================
CREATE TABLE meshmed.medical_documents (
    document_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES meshmed.users(user_id) ON DELETE CASCADE,
    document_type VARCHAR(50) NOT NULL,      -- 'prescription', 'lab_report', etc.
    upload_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    document_date DATE NOT NULL,
    source_provider_encrypted TEXT,          -- PHI: Doctor or Hospital name
    source_provider_type VARCHAR(50),
    raw_text_encrypted TEXT NOT NULL,        -- PHI: Full extracted text from OCR/PDF
    file_hash VARCHAR(64) NOT NULL,          -- SHA-256
    parse_confidence NUMERIC(5,4),
    is_verified BOOLEAN DEFAULT FALSE,
    abha_linked BOOLEAN DEFAULT FALSE,
    language VARCHAR(10) DEFAULT 'en',
    tags JSONB DEFAULT '[]'::jsonb
);
CREATE INDEX idx_medical_documents_user ON meshmed.medical_documents(user_id);
CREATE INDEX idx_medical_documents_date ON meshmed.medical_documents(document_date);

-- =================================================================================
-- PRESCRIPTIONS
-- =================================================================================
CREATE TABLE meshmed.prescriptions (
    prescription_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES meshmed.medical_documents(document_id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES meshmed.users(user_id) ON DELETE CASCADE,
    prescribed_date DATE NOT NULL,
    prescribing_doctor_encrypted TEXT NOT NULL,         -- PHI
    prescribing_doctor_reg_no VARCHAR(100),
    hospital_clinic_encrypted TEXT,                     -- PHI
    diagnosis_mentioned_encrypted TEXT,                 -- PHI
    instructions_encrypted TEXT,                        -- PHI
    follow_up_date DATE,
    follow_up_instructions_encrypted TEXT,              -- PHI
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_prescriptions_user ON meshmed.prescriptions(user_id);

-- =================================================================================
-- MEDICATION ITEMS
-- =================================================================================
CREATE TABLE meshmed.medication_items (
    medication_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prescription_id UUID NOT NULL REFERENCES meshmed.prescriptions(prescription_id) ON DELETE CASCADE,
    brand_name_encrypted TEXT NOT NULL,                 -- PHI
    generic_name VARCHAR(255),                          -- Non-PHI, normalized safe
    dosage_strength VARCHAR(100),
    dosage_form VARCHAR(50),
    frequency VARCHAR(100),
    frequency_normalized VARCHAR(50),
    duration_days INTEGER,
    route VARCHAR(50) DEFAULT 'oral',
    instructions_encrypted TEXT,                        -- PHI
    rxcui VARCHAR(50),                                  -- RxNorm concept ID
    is_current BOOLEAN DEFAULT TRUE,
    started_date DATE,
    stopped_date DATE,
    stopped_reason_encrypted TEXT                       -- PHI
);
CREATE INDEX idx_medications_prescription ON meshmed.medication_items(prescription_id);

-- =================================================================================
-- LAB REPORTS
-- =================================================================================
CREATE TABLE meshmed.lab_reports (
    lab_report_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES meshmed.medical_documents(document_id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES meshmed.users(user_id) ON DELETE CASCADE,
    lab_name_encrypted TEXT NOT NULL,                   -- PHI
    collection_date DATE NOT NULL,
    report_date DATE NOT NULL,
    ordering_doctor_encrypted TEXT,                     -- PHI
    overall_interpretation_encrypted TEXT,              -- PHI
    critical_flags JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- =================================================================================
-- LAB TEST RESULTS
-- =================================================================================
CREATE TABLE meshmed.lab_test_results (
    result_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lab_report_id UUID NOT NULL REFERENCES meshmed.lab_reports(lab_report_id) ON DELETE CASCADE,
    test_name_encrypted TEXT NOT NULL,                  -- PHI (some test names indicate rare diseases)
    test_name_normalized VARCHAR(255),                  -- Normalized safe name
    loinc_code VARCHAR(50),
    value_encrypted TEXT NOT NULL,                      -- PHI: Actual result value
    unit VARCHAR(50),
    reference_range_low NUMERIC,
    reference_range_high NUMERIC,
    reference_range_text VARCHAR(255),
    is_abnormal BOOLEAN NOT NULL DEFAULT FALSE,
    abnormality_direction VARCHAR(20),                  -- 'high', 'low', 'critical_high', 'critical_low'
    methodology VARCHAR(100)
);

-- =================================================================================
-- CARE EPISODES (Longitudinal grouping)
-- =================================================================================
CREATE TABLE meshmed.care_episodes (
    episode_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES meshmed.users(user_id) ON DELETE CASCADE,
    condition_encrypted TEXT,                           -- PHI
    icd10_code VARCHAR(20),
    start_date DATE NOT NULL,
    end_date DATE,
    is_chronic BOOLEAN DEFAULT FALSE,
    managing_doctors_encrypted JSONB,                   -- PHI: list of encrypted strings
    linked_prescriptions JSONB DEFAULT '[]'::jsonb,     -- list of prescription_ids
    linked_lab_reports JSONB DEFAULT '[]'::jsonb,       -- list of lab_report_ids
    summary_encrypted TEXT,                             -- PHI
    status VARCHAR(50) NOT NULL                         -- 'active', 'resolved', 'chronic', 'monitoring'
);

-- =================================================================================
-- DRUG INTERACTION ALERTS
-- =================================================================================
CREATE TABLE meshmed.drug_interaction_alerts (
    alert_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES meshmed.users(user_id) ON DELETE CASCADE,
    drug_a VARCHAR(255) NOT NULL,
    drug_b VARCHAR(255) NOT NULL,
    interaction_severity VARCHAR(50) NOT NULL,          -- 'contraindicated', 'major', 'moderate', 'minor'
    mechanism TEXT NOT NULL,
    clinical_effect TEXT NOT NULL,
    recommendation TEXT NOT NULL,
    source VARCHAR(50) NOT NULL,
    detected_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_by_doctor BOOLEAN DEFAULT FALSE
);

-- =================================================================================
-- HANDOFF PACKETS (Coordination Layer)
-- =================================================================================
CREATE TABLE meshmed.handoff_packets (
    packet_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES meshmed.users(user_id) ON DELETE CASCADE,
    generated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    target_provider_specialty VARCHAR(100),
    pdf_path TEXT,                                      -- Secure storage bucket path
    whatsapp_summary_encrypted TEXT,                    -- PHI
    was_delivered BOOLEAN DEFAULT FALSE,
    delivered_at TIMESTAMP WITH TIME ZONE
);

-- =================================================================================
-- ABHA SYNC LOG
-- =================================================================================
CREATE TABLE meshmed.abha_sync_log (
    sync_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES meshmed.users(user_id) ON DELETE CASCADE,
    sync_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    direction VARCHAR(20) NOT NULL,                     -- 'pull' or 'push'
    records_synced INTEGER DEFAULT 0,
    status VARCHAR(20) NOT NULL,                        -- 'success', 'failed'
    error_message TEXT
);

-- =================================================================================
-- LOCAL DRUG INTERACTION KNOWLEDGE BASE (Seed table)
-- =================================================================================
CREATE TABLE meshmed.drug_interactions_kb (
    id SERIAL PRIMARY KEY,
    drug_a VARCHAR(255) NOT NULL,
    drug_b VARCHAR(255) NOT NULL,
    interaction_severity VARCHAR(50) NOT NULL,
    technical_mechanism TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_interaction_lookup ON meshmed.drug_interactions_kb(drug_a, drug_b);
