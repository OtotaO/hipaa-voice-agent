#!/bin/bash

# Generate TLS Certificates Script
# Creates self-signed certificates for development or assists with production setup

set -euo pipefail

ENVIRONMENT="${1:-development}"
CERT_DIR="config/certs"
DOMAIN="${2:-localhost}"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

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

# Create certificate directory
mkdir -p "$CERT_DIR"

if [ "$ENVIRONMENT" = "production" ]; then
    log_info "Production Certificate Setup"
    echo
    echo "For production, you should use certificates from a trusted CA."
    echo
    echo "Option 1: Let's Encrypt (Recommended)"
    echo "========================================="
    echo "1. Install certbot:"
    echo "   sudo apt install certbot"
    echo
    echo "2. Generate certificate:"
    echo "   sudo certbot certonly --standalone -d $DOMAIN"
    echo
    echo "3. Copy certificates:"
    echo "   sudo cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem $CERT_DIR/server.crt"
    echo "   sudo cp /etc/letsencrypt/live/$DOMAIN/privkey.pem $CERT_DIR/server.key"
    echo "   sudo chmod 600 $CERT_DIR/server.key"
    echo
    echo "4. Set up auto-renewal:"
    echo "   sudo crontab -e"
    echo "   Add: 0 0 1 * * certbot renew --quiet"
    echo
    echo "Option 2: Commercial Certificate"
    echo "========================================="
    echo "1. Generate CSR:"
    echo "   openssl req -new -newkey rsa:2048 -nodes -keyout $CERT_DIR/server.key -out $CERT_DIR/server.csr"
    echo
    echo "2. Submit CSR to your CA"
    echo
    echo "3. Save certificate as $CERT_DIR/server.crt"
    echo
    
    # Check if user wants to generate CSR
    read -p "Generate CSR now? (y/n): " generate_csr
    if [ "$generate_csr" = "y" ]; then
        openssl req -new -newkey rsa:4096 -nodes \
            -keyout "$CERT_DIR/server.key" \
            -out "$CERT_DIR/server.csr" \
            -subj "/C=US/ST=Kentucky/L=Louisville/O=Medical Office/CN=$DOMAIN"
        
        chmod 600 "$CERT_DIR/server.key"
        log_info "CSR generated at $CERT_DIR/server.csr"
        log_info "Submit this to your Certificate Authority"
    fi
    
elif [ "$ENVIRONMENT" = "development" ]; then
    log_info "Generating self-signed certificate for development"
    
    # Generate private key
    openssl genrsa -out "$CERT_DIR/server.key" 4096
    
    # Generate certificate configuration
    cat > "$CERT_DIR/cert.conf" << EOF
[req]
default_bits = 4096
prompt = no
default_md = sha256
distinguished_name = dn
req_extensions = v3_req

[dn]
C = US
ST = Kentucky
L = Louisville
O = Medical Office Development
CN = $DOMAIN

[v3_req]
subjectAltName = @alt_names

[alt_names]
DNS.1 = $DOMAIN
DNS.2 = *.$DOMAIN
DNS.3 = localhost
IP.1 = 127.0.0.1
IP.2 = ::1
EOF
    
    # Generate self-signed certificate
    openssl req -new -x509 -sha256 -days 365 \
        -key "$CERT_DIR/server.key" \
        -out "$CERT_DIR/server.crt" \
        -config "$CERT_DIR/cert.conf" \
        -extensions v3_req
    
    # Set permissions
    chmod 600 "$CERT_DIR/server.key"
    chmod 644 "$CERT_DIR/server.crt"
    
    # Generate Diffie-Hellman parameters for extra security
    log_info "Generating DH parameters (this may take a few minutes)..."
    openssl dhparam -out "$CERT_DIR/dhparam.pem" 2048
    
    log_info "Self-signed certificate generated successfully"
    log_warn "This certificate is for development only!"
    
    # Display certificate info
    echo
    echo "Certificate Information:"
    echo "========================"
    openssl x509 -in "$CERT_DIR/server.crt" -noout -subject -dates
    
else
    log_error "Unknown environment: $ENVIRONMENT (use 'development' or 'production')"
fi

# Create certificate chain file for compatibility
if [ -f "$CERT_DIR/server.crt" ]; then
    cp "$CERT_DIR/server.crt" "$CERT_DIR/fullchain.pem"
    log_info "Certificate chain created at $CERT_DIR/fullchain.pem"
fi

# Verify certificate
if [ -f "$CERT_DIR/server.crt" ] && [ -f "$CERT_DIR/server.key" ]; then
    log_info "Verifying certificate and key match..."
    
    cert_modulus=$(openssl x509 -noout -modulus -in "$CERT_DIR/server.crt" | openssl md5)
    key_modulus=$(openssl rsa -noout -modulus -in "$CERT_DIR/server.key" | openssl md5)
    
    if [ "$cert_modulus" = "$key_modulus" ]; then
        log_info "Certificate and key match ✓"
    else
        log_error "Certificate and key do not match!"
    fi
fi

echo
log_info "Certificate setup complete!"
echo
echo "Files created:"
echo "  - $CERT_DIR/server.crt (certificate)"
echo "  - $CERT_DIR/server.key (private key)"
if [ "$ENVIRONMENT" = "development" ]; then
    echo "  - $CERT_DIR/dhparam.pem (DH parameters)"
fi
echo
echo "Next steps:"
echo "1. Update config/.env with TLS settings:"
echo "   PIPECAT_TLS_ENABLED=true"
echo "   PIPECAT_TLS_CERT=/app/config/certs/server.crt"
echo "   PIPECAT_TLS_KEY=/app/config/certs/server.key"
echo
echo "2. Restart services:"
echo "   make restart"
