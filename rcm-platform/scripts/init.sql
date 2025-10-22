-- RCM Platform Database Initialization
-- Extends Medplum's FHIR schema with RCM-specific tables

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Eligibility Cache (saves Stedi API calls)
CREATE TABLE IF NOT EXISTS eligibility_cache (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_id VARCHAR(255) NOT NULL,
    payer_id VARCHAR(100),
    check_date TIMESTAMP DEFAULT NOW(),
    coverage_status VARCHAR(20),
    plan_name VARCHAR(255),
    copay VARCHAR(50),
    deductible VARCHAR(50),
    out_of_pocket_max VARCHAR(50),
    response_data JSONB,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT fk_patient FOREIGN KEY (patient_id) REFERENCES "Patient"(id) ON DELETE CASCADE
);

CREATE INDEX idx_eligibility_patient ON eligibility_cache(patient_id);
CREATE INDEX idx_eligibility_expires ON eligibility_cache(expires_at);
CREATE INDEX idx_eligibility_check_date ON eligibility_cache(check_date DESC);

-- Claim Scrub Results (AI scrubber logs)
CREATE TABLE IF NOT EXISTS claim_scrub_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    claim_data JSONB NOT NULL,
    scrub_result JSONB NOT NULL,
    ready_to_submit BOOLEAN,
    confidence_score DECIMAL(3,2),
    errors_found TEXT[],
    warnings_found TEXT[],
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_scrub_ready ON claim_scrub_logs(ready_to_submit);
CREATE INDEX idx_scrub_created ON claim_scrub_logs(created_at DESC);

-- Claims Tracking (extends FHIR Claim resource)
CREATE TABLE IF NOT EXISTS claims_tracking (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    fhir_claim_id VARCHAR(255) NOT NULL,
    patient_id VARCHAR(255) NOT NULL,
    submission_status VARCHAR(50),
    clearinghouse_id VARCHAR(100),
    stedi_transaction_id VARCHAR(100),
    submitted_at TIMESTAMP,
    acknowledged_at TIMESTAMP,
    paid_at TIMESTAMP,
    denial_reason TEXT,
    appeal_status VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_claims_patient ON claims_tracking(patient_id);
CREATE INDEX idx_claims_status ON claims_tracking(submission_status);
CREATE INDEX idx_claims_submitted ON claims_tracking(submitted_at DESC);

-- Audit Log (HIPAA compliance)
CREATE TABLE IF NOT EXISTS audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(255),
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50),
    resource_id VARCHAR(255),
    ip_address INET,
    user_agent TEXT,
    request_data JSONB,
    response_status INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_audit_user ON audit_log(user_id);
CREATE INDEX idx_audit_action ON audit_log(action);
CREATE INDEX idx_audit_created ON audit_log(created_at DESC);

-- Practice Settings
CREATE TABLE IF NOT EXISTS practice_settings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    practice_name VARCHAR(255) NOT NULL,
    npi VARCHAR(10) NOT NULL UNIQUE,
    tax_id VARCHAR(20),
    address TEXT,
    phone VARCHAR(20),
    email VARCHAR(255),
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Insert default practice
INSERT INTO practice_settings (practice_name, npi, settings)
VALUES (
    'Demo Practice',
    '1234567890',
    '{"ai_scrubber_enabled": true, "cache_eligibility": true}'
)
ON CONFLICT (npi) DO NOTHING;

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers for updated_at
CREATE TRIGGER update_claims_tracking_updated_at BEFORE UPDATE ON claims_tracking
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_practice_settings_updated_at BEFORE UPDATE ON practice_settings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Materialized view for dashboard metrics (updated daily)
CREATE MATERIALIZED VIEW IF NOT EXISTS daily_metrics AS
SELECT
    DATE(created_at) as metric_date,
    COUNT(*) as total_claims,
    COUNT(*) FILTER (WHERE ready_to_submit = true) as clean_claims,
    COUNT(*) FILTER (WHERE ready_to_submit = false) as flagged_claims,
    ROUND(AVG(confidence_score), 2) as avg_confidence
FROM claim_scrub_logs
GROUP BY DATE(created_at)
ORDER BY metric_date DESC;

CREATE UNIQUE INDEX ON daily_metrics (metric_date);

-- Grant permissions (if using specific user)
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO medplum;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO medplum;
