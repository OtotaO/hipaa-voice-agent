#!/bin/bash

# HIPAA Voice Agent - Deployment Script
# Production deployment with security hardening

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT="${1:-production}"
CONFIG_FILE="config/.env"
BACKUP_DIR="backups/$(date +%Y%m%d_%H%M%S)"

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed"
    fi
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed"
    fi
    
    # Check environment file
    if [ ! -f "$CONFIG_FILE" ]; then
        log_error "Configuration file not found: $CONFIG_FILE"
    fi
    
    # Check required environment variables
    required_vars=(
        "TWILIO_ACCOUNT_SID"
        "TWILIO_AUTH_TOKEN"
        "TWILIO_HIPAA_PROJECT_ID"
        "AWS_ACCESS_KEY_ID"
        "AWS_SECRET_ACCESS_KEY"
        "MASTER_ENCRYPTION_KEY"
        "POSTGRES_PASSWORD"
        "REDIS_PASSWORD"
    )
    
    source "$CONFIG_FILE"
    
    for var in "${required_vars[@]}"; do
        if [ -z "${!var:-}" ]; then
            log_error "Required environment variable not set: $var"
        fi
    done
    
    log_info "Prerequisites check passed"
}

validate_hipaa_compliance() {
    log_info "Validating HIPAA compliance settings..."
    
    source "$CONFIG_FILE"
    
    # Check encryption settings
    if [ "${AUDIT_ENABLED:-false}" != "true" ]; then
        log_error "Audit logging must be enabled for HIPAA compliance"
    fi
    
    if [ "${PHI_REDACTION_ENABLED:-false}" != "true" ]; then
        log_error "PHI redaction must be enabled for HIPAA compliance"
    fi
    
    if [ "${PIPECAT_TLS_ENABLED:-false}" != "true" ]; then
        log_error "TLS must be enabled for HIPAA compliance"
    fi
    
    # Check retention settings
    if [ "${AUDIT_LOG_RETENTION_DAYS:-0}" -lt 2555 ]; then
        log_warn "Audit log retention should be at least 7 years (2555 days) for HIPAA"
    fi
    
    # Check BAA configuration
    if [ -z "${TWILIO_HIPAA_PROJECT_ID:-}" ]; then
        log_error "Twilio HIPAA Project ID must be configured"
    fi
    
    log_info "HIPAA compliance validation passed"
}

backup_existing() {
    log_info "Creating backup of existing deployment..."
    
    mkdir -p "$BACKUP_DIR"
    
    # Backup database
    if docker ps | grep -q hipaa-postgres; then
        log_info "Backing up database..."
        docker exec hipaa-postgres pg_dumpall -U postgres > "$BACKUP_DIR/database.sql"
    fi
    
    # Backup configuration
    cp -r config "$BACKUP_DIR/" 2>/dev/null || true
    
    # Backup logs (without PHI)
    if [ -d "data/logs" ]; then
        tar -czf "$BACKUP_DIR/logs.tar.gz" data/logs --exclude="*.audit"
    fi
    
    log_info "Backup created at: $BACKUP_DIR"
}

generate_certificates() {
    log_info "Generating TLS certificates..."
    
    CERT_DIR="config/certs"
    mkdir -p "$CERT_DIR"
    
    # Check if certificates already exist
    if [ -f "$CERT_DIR/server.crt" ] && [ -f "$CERT_DIR/server.key" ]; then
        log_info "Certificates already exist, skipping generation"
        return
    fi
    
    # Generate self-signed certificate for development
    # In production, use proper certificates from a CA
    if [ "$ENVIRONMENT" = "development" ]; then
        openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
            -keyout "$CERT_DIR/server.key" \
            -out "$CERT_DIR/server.crt" \
            -subj "/C=US/ST=KY/L=Louisville/O=Medical Office/CN=localhost"
        
        # Set proper permissions
        chmod 600 "$CERT_DIR/server.key"
        chmod 644 "$CERT_DIR/server.crt"
        
        log_warn "Using self-signed certificate for development"
    else
        log_error "Production certificates not found. Please install proper TLS certificates in $CERT_DIR"
    fi
}

setup_data_directories() {
    log_info "Setting up data directories..."
    
    # Create required directories
    directories=(
        "data/postgres"
        "data/logs/pipecat"
        "data/logs/audit"
        "data/models"
        "data/backups"
        "data/temp"
    )
    
    for dir in "${directories[@]}"; do
        mkdir -p "$dir"
        # Set restrictive permissions for sensitive directories
        if [[ "$dir" == *"audit"* ]] || [[ "$dir" == *"postgres"* ]]; then
            chmod 700 "$dir"
        else
            chmod 755 "$dir"
        fi
    done
    
    log_info "Data directories created"
}

deploy_services() {
    log_info "Deploying services..."
    
    # Set environment
    export ENVIRONMENT="$ENVIRONMENT"
    
    # Pull latest images
    log_info "Pulling Docker images..."
    docker-compose pull
    
    # Build custom images
    log_info "Building custom images..."
    docker-compose build --no-cache
    
    # Start services
    log_info "Starting services..."
    
    # Start infrastructure services first
    docker-compose up -d postgres redis
    
    # Wait for database to be ready
    log_info "Waiting for database..."
    sleep 10
    
    # Run database migrations
    # docker-compose run --rm pipecat python -m alembic upgrade head
    
    # Start Temporal
    docker-compose up -d temporal
    sleep 10
    
    # Start remaining services
    if [ "$ENVIRONMENT" = "production" ]; then
        docker-compose up -d \
            pipecat \
            vllm \
            temporal-worker \
            fhir-bridge \
            vector
    else
        docker-compose --profile development up -d
    fi
    
    log_info "Services deployed"
}

verify_deployment() {
    log_info "Verifying deployment..."
    
    # Wait for services to start
    sleep 30
    
    # Check service health
    services=(
        "hipaa-pipecat:8081/health"
        "hipaa-temporal:7233"
        "hipaa-postgres:5432"
        "hipaa-redis:6379"
    )
    
    failed=0
    for service in "${services[@]}"; do
        IFS=':' read -r container port <<< "$service"
        if docker ps | grep -q "$container"; then
            log_info "$container is running"
            
            # Check if port is responding
            if [[ "$port" == *"/health"* ]]; then
                # HTTP health check
                port_num="${port%%/*}"
                if curl -f "http://localhost:$port" &>/dev/null; then
                    log_info "$container health check passed"
                else
                    log_warn "$container health check failed"
                    ((failed++))
                fi
            fi
        else
            log_error "$container is not running"
            ((failed++))
        fi
    done
    
    if [ $failed -gt 0 ]; then
        log_error "Deployment verification failed. Check logs with: docker-compose logs"
    fi
    
    log_info "Deployment verification completed"
}

run_compliance_check() {
    log_info "Running HIPAA compliance check..."
    
    # Wait for API to be ready
    sleep 10
    
    # Call compliance endpoint
    response=$(curl -s -H "Authorization: Bearer ${API_KEY:-test}" \
        http://localhost:8080/compliance || echo "{}")
    
    # Check if compliant
    if echo "$response" | grep -q '"compliant":true'; then
        log_info "HIPAA compliance check passed"
    else
        log_warn "HIPAA compliance issues detected:"
        echo "$response" | python -m json.tool
    fi
}

setup_monitoring() {
    log_info "Setting up monitoring..."
    
    if [ "$ENVIRONMENT" = "production" ]; then
        # Start monitoring stack
        docker-compose --profile monitoring up -d prometheus grafana
        
        log_info "Monitoring available at:"
        log_info "  - Prometheus: http://localhost:9090"
        log_info "  - Grafana: http://localhost:3000"
        log_info "  Default Grafana credentials: admin / ${GRAFANA_PASSWORD:-admin}"
    else
        log_info "Skipping monitoring setup for development environment"
    fi
}

setup_scheduled_tasks() {
    log_info "Setting up scheduled tasks..."
    
    # Create cron jobs for maintenance
    cat > /tmp/hipaa-cron << EOF
# HIPAA Voice Agent Scheduled Tasks

# Daily backup at 2 AM
0 2 * * * cd $(pwd) && ./scripts/backup.sh

# Weekly compliance audit
0 3 * * 0 cd $(pwd) && ./scripts/compliance-audit.sh

# Log rotation (keep 90 days)
0 4 * * * find $(pwd)/data/logs -name "*.log" -mtime +90 -delete

# Certificate renewal check (monthly)
0 0 1 * * cd $(pwd) && ./scripts/check-certificates.sh
EOF
    
    # Install cron jobs
    if [ "$ENVIRONMENT" = "production" ]; then
        crontab /tmp/hipaa-cron
        log_info "Scheduled tasks installed"
    else
        log_info "Scheduled tasks configuration saved to /tmp/hipaa-cron"
    fi
}

print_summary() {
    echo
    echo "=========================================="
    echo "   HIPAA Voice Agent Deployment Complete"
    echo "=========================================="
    echo
    echo "Environment: $ENVIRONMENT"
    echo
    echo "Services:"
    echo "  - API: http://localhost:8080"
    echo "  - WebSocket: wss://localhost:8080/ws"
    echo "  - Health: http://localhost:8081/health"
    echo
    if [ "$ENVIRONMENT" = "development" ]; then
        echo "Development Tools:"
        echo "  - API Docs: http://localhost:8080/docs"
        echo "  - Temporal UI: http://localhost:8088"
    fi
    echo
    echo "Commands:"
    echo "  - View logs: docker-compose logs -f [service]"
    echo "  - Stop services: docker-compose down"
    echo "  - Restart service: docker-compose restart [service]"
    echo "  - Run compliance check: curl http://localhost:8080/compliance"
    echo
    echo "Next Steps:"
    echo "  1. Verify all BAAs are signed with service providers"
    echo "  2. Configure phone numbers in Twilio Console"
    echo "  3. Test with: ./scripts/test-call.sh"
    echo "  4. Monitor logs for any errors"
    echo
    log_warn "Remember to:"
    log_warn "  - Rotate credentials regularly"
    log_warn "  - Review audit logs daily"
    log_warn "  - Keep all software updated"
    log_warn "  - Conduct regular security audits"
}

# Main deployment flow
main() {
    log_info "Starting HIPAA Voice Agent deployment for $ENVIRONMENT environment"
    
    check_prerequisites
    validate_hipaa_compliance
    
    if [ "$ENVIRONMENT" = "production" ]; then
        backup_existing
    fi
    
    generate_certificates
    setup_data_directories
    deploy_services
    verify_deployment
    run_compliance_check
    setup_monitoring
    setup_scheduled_tasks
    
    print_summary
    
    log_info "Deployment completed successfully!"
}

# Run main function
main "$@"
