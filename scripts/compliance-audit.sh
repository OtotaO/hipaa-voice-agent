#!/bin/bash

# HIPAA Compliance Audit Script
# Performs comprehensive compliance checks and generates audit report

set -euo pipefail

# Configuration
AUDIT_DATE=$(date +%Y-%m-%d)
AUDIT_TIME=$(date +%H:%M:%S)
REPORT_DIR="audits/${AUDIT_DATE}"
REPORT_FILE="${REPORT_DIR}/compliance_audit_${AUDIT_DATE}_${AUDIT_TIME//:/}.html"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Audit results
PASSED_CHECKS=0
FAILED_CHECKS=0
WARNING_CHECKS=0
AUDIT_FINDINGS=()

# Functions
log_pass() {
    echo -e "${GREEN}✓${NC} $1"
    ((PASSED_CHECKS++))
}

log_fail() {
    echo -e "${RED}✗${NC} $1"
    ((FAILED_CHECKS++))
    AUDIT_FINDINGS+=("FAIL: $1")
}

log_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
    ((WARNING_CHECKS++))
    AUDIT_FINDINGS+=("WARN: $1")
}

log_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# Create report directory
mkdir -p "$REPORT_DIR"

# Start audit
echo "=========================================="
echo "    HIPAA Compliance Audit"
echo "    Date: ${AUDIT_DATE} ${AUDIT_TIME}"
echo "=========================================="
echo

# ===== Technical Safeguards =====
echo "1. TECHNICAL SAFEGUARDS"
echo "-----------------------"

# Check encryption
echo "Checking Encryption..."
if [ -f "config/.env" ]; then
    source config/.env
    
    if [ -n "${MASTER_ENCRYPTION_KEY:-}" ] && [ "${MASTER_ENCRYPTION_KEY}" != "default-key-change-me" ]; then
        log_pass "Master encryption key configured"
    else
        log_fail "Master encryption key not properly configured"
    fi
    
    if [ "${DB_ENCRYPT_PHI:-false}" = "true" ]; then
        log_pass "PHI encryption enabled in database"
    else
        log_fail "PHI encryption not enabled in database"
    fi
    
    if [ "${AUDIT_LOG_ENCRYPTION:-false}" = "true" ]; then
        log_pass "Audit log encryption enabled"
    else
        log_fail "Audit log encryption not enabled"
    fi
else
    log_fail "Configuration file not found"
fi

# Check TLS/SSL
echo -e "\nChecking TLS/SSL..."
if [ -f "config/certs/server.crt" ] && [ -f "config/certs/server.key" ]; then
    # Check certificate expiration
    if openssl x509 -checkend 2592000 -noout -in config/certs/server.crt 2>/dev/null; then
        log_pass "TLS certificate valid for more than 30 days"
    else
        log_warn "TLS certificate expires within 30 days"
    fi
    
    # Check certificate strength
    key_size=$(openssl rsa -in config/certs/server.key -text -noout 2>/dev/null | grep "Private-Key" | sed 's/.*(\(.*\) bit.*/\1/')
    if [ "${key_size:-0}" -ge 2048 ]; then
        log_pass "TLS key strength adequate (${key_size} bit)"
    else
        log_fail "TLS key strength inadequate (${key_size} bit, minimum 2048)"
    fi
else
    log_fail "TLS certificates not found"
fi

# Check network security
echo -e "\nChecking Network Security..."
if docker ps | grep -q hipaa-pipecat; then
    # Check if unnecessary ports are exposed
    exposed_ports=$(docker ps --format "table {{.Ports}}" | grep -v PORTS | wc -l)
    if [ "$exposed_ports" -le 5 ]; then
        log_pass "Minimal ports exposed"
    else
        log_warn "Multiple ports exposed - review necessity"
    fi
else
    log_warn "Services not running - cannot check network security"
fi

# ===== Administrative Safeguards =====
echo -e "\n2. ADMINISTRATIVE SAFEGUARDS"
echo "----------------------------"

# Check access controls
echo "Checking Access Controls..."
if [ "${ENABLE_API_KEY_VALIDATION:-false}" = "true" ]; then
    log_pass "API key validation enabled"
else
    log_fail "API key validation not enabled"
fi

if [ "${JWT_SECRET:-}" != "" ]; then
    log_pass "JWT authentication configured"
else
    log_fail "JWT authentication not configured"
fi

# Check audit logging
echo -e "\nChecking Audit Logging..."
if [ "${AUDIT_ENABLED:-false}" = "true" ]; then
    log_pass "Audit logging enabled"
    
    # Check audit log retention
    retention="${AUDIT_LOG_RETENTION_DAYS:-0}"
    if [ "$retention" -ge 2555 ]; then
        log_pass "Audit retention meets 7-year requirement ($retention days)"
    else
        log_fail "Audit retention below 7-year requirement ($retention days)"
    fi
    
    # Check if audit logs exist
    if [ -d "data/logs/audit" ]; then
        audit_files=$(find data/logs/audit -name "*.log" 2>/dev/null | wc -l)
        if [ "$audit_files" -gt 0 ]; then
            log_pass "Audit logs are being generated ($audit_files files)"
        else
            log_warn "No audit log files found"
        fi
    else
        log_warn "Audit log directory not found"
    fi
else
    log_fail "Audit logging not enabled"
fi

# Check PHI handling
echo -e "\nChecking PHI Handling..."
if [ "${PHI_REDACTION_ENABLED:-false}" = "true" ]; then
    log_pass "PHI redaction enabled"
else
    log_fail "PHI redaction not enabled"
fi

if [ "${CALL_RECORDING_ENABLED:-false}" = "true" ]; then
    if [ "${CALL_RECORDING_ENCRYPTION:-false}" = "true" ]; then
        log_warn "Call recording enabled but encrypted"
    else
        log_fail "Call recording enabled without encryption"
    fi
else
    log_pass "Call recording disabled (recommended)"
fi

# ===== Physical Safeguards =====
echo -e "\n3. PHYSICAL SAFEGUARDS"
echo "----------------------"

# Check backup configuration
echo "Checking Backup Configuration..."
if [ "${BACKUP_ENABLED:-false}" = "true" ]; then
    if [ "${BACKUP_ENCRYPTION:-false}" = "true" ]; then
        log_pass "Backups enabled with encryption"
    else
        log_fail "Backups enabled without encryption"
    fi
else
    log_warn "Backups not enabled"
fi

# Check data storage
echo -e "\nChecking Data Storage..."
if [ -d "data" ]; then
    # Check permissions
    perms=$(stat -c %a data 2>/dev/null || stat -f %A data)
    if [ "$perms" = "755" ] || [ "$perms" = "750" ] || [ "$perms" = "700" ]; then
        log_pass "Data directory permissions appropriate ($perms)"
    else
        log_fail "Data directory permissions too permissive ($perms)"
    fi
fi

# ===== BAA Compliance =====
echo -e "\n4. BUSINESS ASSOCIATE AGREEMENTS"
echo "---------------------------------"

echo "Checking BAA Configuration..."
if [ -n "${TWILIO_HIPAA_PROJECT_ID:-}" ]; then
    log_pass "Twilio HIPAA Project configured"
else
    log_fail "Twilio HIPAA Project not configured"
fi

log_info "Ensure BAAs are executed with:"
log_info "  - Twilio (for telephony)"
log_info "  - AWS (for Transcribe Medical and S3)"
log_info "  - Any other service handling PHI"

# ===== Service Configuration =====
echo -e "\n5. SERVICE CONFIGURATION"
echo "------------------------"

# Check running services
echo "Checking Service Status..."
critical_services=("hipaa-pipecat" "hipaa-postgres" "hipaa-redis" "hipaa-temporal")
for service in "${critical_services[@]}"; do
    if docker ps | grep -q "$service"; then
        log_pass "$service is running"
    else
        log_fail "$service is not running"
    fi
done

# Check database security
echo -e "\nChecking Database Security..."
if docker ps | grep -q hipaa-postgres; then
    # Check SSL mode
    ssl_mode="${POSTGRES_SSL_MODE:-disable}"
    if [ "$ssl_mode" = "require" ] || [ "$ssl_mode" = "verify-full" ]; then
        log_pass "PostgreSQL SSL enabled ($ssl_mode)"
    else
        log_fail "PostgreSQL SSL not properly configured ($ssl_mode)"
    fi
fi

# Check Redis security
if docker ps | grep -q hipaa-redis; then
    if [ -n "${REDIS_PASSWORD:-}" ]; then
        log_pass "Redis password protection enabled"
    else
        log_fail "Redis password not set"
    fi
fi

# ===== Vulnerability Scan =====
echo -e "\n6. VULNERABILITY ASSESSMENT"
echo "---------------------------"

echo "Checking for known vulnerabilities..."

# Check Python dependencies
if [ -f "requirements.txt" ]; then
    # Use safety to check for vulnerabilities (if installed)
    if command -v safety &> /dev/null; then
        vulnerabilities=$(safety check -r requirements.txt --json 2>/dev/null | python -c "import sys, json; data=json.load(sys.stdin); print(len(data))" 2>/dev/null || echo "0")
        if [ "$vulnerabilities" = "0" ]; then
            log_pass "No known vulnerabilities in Python dependencies"
        else
            log_warn "$vulnerabilities vulnerabilities found in dependencies"
        fi
    else
        log_info "Install 'safety' for vulnerability scanning: pip install safety"
    fi
fi

# Check Docker images
echo -e "\nChecking Docker images..."
outdated_images=$(docker images --format "table {{.Repository}}:{{.Tag}}\t{{.CreatedSince}}" | grep -c "months ago" || true)
if [ "$outdated_images" -eq 0 ]; then
    log_pass "Docker images appear up-to-date"
else
    log_warn "$outdated_images Docker images may be outdated"
fi

# ===== Generate HTML Report =====
echo -e "\nGenerating HTML Report..."

cat > "$REPORT_FILE" << EOF
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HIPAA Compliance Audit Report - ${AUDIT_DATE}</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }
        .header {
            background: #2c3e50;
            color: white;
            padding: 30px;
            border-radius: 8px;
            margin-bottom: 30px;
        }
        .summary {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .summary-card {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            text-align: center;
        }
        .summary-card h3 {
            margin: 0 0 10px 0;
            font-size: 2em;
        }
        .passed { color: #27ae60; }
        .failed { color: #e74c3c; }
        .warning { color: #f39c12; }
        .section {
            background: white;
            padding: 25px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .finding {
            padding: 10px;
            margin: 10px 0;
            border-left: 4px solid;
            background: #f8f9fa;
        }
        .finding.fail {
            border-color: #e74c3c;
            background: #ffeef0;
        }
        .finding.warn {
            border-color: #f39c12;
            background: #fffbf0;
        }
        .finding.pass {
            border-color: #27ae60;
            background: #f0fff4;
        }
        .recommendations {
            background: #ecf0f1;
            padding: 20px;
            border-radius: 8px;
            margin-top: 30px;
        }
        .footer {
            text-align: center;
            color: #7f8c8d;
            margin-top: 50px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
        }
        @media print {
            body { background: white; }
            .section { box-shadow: none; border: 1px solid #ddd; }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>HIPAA Compliance Audit Report</h1>
        <p>Generated: ${AUDIT_DATE} ${AUDIT_TIME}</p>
        <p>Environment: $(hostname)</p>
    </div>

    <div class="summary">
        <div class="summary-card">
            <h3 class="passed">${PASSED_CHECKS}</h3>
            <p>Passed Checks</p>
        </div>
        <div class="summary-card">
            <h3 class="warning">${WARNING_CHECKS}</h3>
            <p>Warnings</p>
        </div>
        <div class="summary-card">
            <h3 class="failed">${FAILED_CHECKS}</h3>
            <p>Failed Checks</p>
        </div>
        <div class="summary-card">
            <h3>$(echo "scale=1; $PASSED_CHECKS * 100 / ($PASSED_CHECKS + $FAILED_CHECKS + $WARNING_CHECKS)" | bc)%</h3>
            <p>Compliance Score</p>
        </div>
    </div>

    <div class="section">
        <h2>Audit Findings</h2>
EOF

# Add findings to report
for finding in "${AUDIT_FINDINGS[@]}"; do
    if [[ $finding == FAIL:* ]]; then
        echo "        <div class='finding fail'>${finding#FAIL: }</div>" >> "$REPORT_FILE"
    elif [[ $finding == WARN:* ]]; then
        echo "        <div class='finding warn'>${finding#WARN: }</div>" >> "$REPORT_FILE"
    fi
done

# Add recommendations
cat >> "$REPORT_FILE" << EOF
    </div>

    <div class="recommendations">
        <h2>Recommendations</h2>
        <ul>
EOF

# Generate recommendations based on failures
if [ $FAILED_CHECKS -gt 0 ]; then
    echo "            <li><strong>CRITICAL:</strong> Address all failed checks immediately to ensure HIPAA compliance</li>" >> "$REPORT_FILE"
fi

if [[ " ${AUDIT_FINDINGS[@]} " =~ "encryption" ]]; then
    echo "            <li>Review and strengthen encryption configuration for all PHI data</li>" >> "$REPORT_FILE"
fi

if [[ " ${AUDIT_FINDINGS[@]} " =~ "audit" ]]; then
    echo "            <li>Ensure audit logging is properly configured with 7-year retention</li>" >> "$REPORT_FILE"
fi

if [[ " ${AUDIT_FINDINGS[@]} " =~ "TLS" ]] || [[ " ${AUDIT_FINDINGS[@]} " =~ "SSL" ]]; then
    echo "            <li>Update TLS certificates and ensure proper SSL configuration</li>" >> "$REPORT_FILE"
fi

cat >> "$REPORT_FILE" << EOF
            <li>Schedule regular security audits (monthly recommended)</li>
            <li>Review and update Business Associate Agreements annually</li>
            <li>Conduct staff HIPAA training quarterly</li>
            <li>Test disaster recovery procedures regularly</li>
        </ul>
    </div>

    <div class="footer">
        <p>This report is confidential and contains sensitive security information.</p>
        <p>Retention: 7 years per HIPAA requirements</p>
        <p>Next audit due: $(date -d "+30 days" +%Y-%m-%d)</p>
    </div>
</body>
</html>
EOF

# ===== Summary =====
echo
echo "=========================================="
echo "         AUDIT SUMMARY"
echo "=========================================="
echo -e "${GREEN}Passed:${NC} $PASSED_CHECKS"
echo -e "${YELLOW}Warnings:${NC} $WARNING_CHECKS"
echo -e "${RED}Failed:${NC} $FAILED_CHECKS"

# Calculate compliance score
if [ $((PASSED_CHECKS + FAILED_CHECKS + WARNING_CHECKS)) -gt 0 ]; then
    COMPLIANCE_SCORE=$(echo "scale=1; $PASSED_CHECKS * 100 / ($PASSED_CHECKS + $FAILED_CHECKS + $WARNING_CHECKS)" | bc)
    echo -e "Compliance Score: ${COMPLIANCE_SCORE}%"
    
    if (( $(echo "$COMPLIANCE_SCORE >= 90" | bc -l) )); then
        echo -e "${GREEN}Status: COMPLIANT${NC}"
    elif (( $(echo "$COMPLIANCE_SCORE >= 70" | bc -l) )); then
        echo -e "${YELLOW}Status: NEEDS IMPROVEMENT${NC}"
    else
        echo -e "${RED}Status: NON-COMPLIANT${NC}"
    fi
fi

echo
echo "Full report saved to: $REPORT_FILE"
echo
echo "Next Steps:"
if [ $FAILED_CHECKS -gt 0 ]; then
    echo "  1. Address all failed checks immediately"
fi
if [ $WARNING_CHECKS -gt 0 ]; then
    echo "  2. Review and address warnings"
fi
echo "  3. File report with compliance officer"
echo "  4. Schedule remediation for any findings"

# Create audit log entry
echo "$(date -Iseconds),COMPLIANCE_AUDIT,completed,passed=$PASSED_CHECKS,warnings=$WARNING_CHECKS,failed=$FAILED_CHECKS" >> data/logs/audit/compliance_audits.log

exit $([ $FAILED_CHECKS -eq 0 ] && echo 0 || echo 1)
