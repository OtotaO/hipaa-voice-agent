# HIPAA Voice Agent - Complete Setup Guide

## 📋 Table of Contents
1. [Prerequisites](#prerequisites)
2. [Initial Setup](#initial-setup)
3. [Twilio Configuration](#twilio-configuration)
4. [AWS Configuration](#aws-configuration)
5. [Self-Hosted LLM Setup](#self-hosted-llm-setup)
6. [FHIR Integration](#fhir-integration)
7. [Security Configuration](#security-configuration)
8. [Deployment](#deployment)
9. [Testing](#testing)
10. [Monitoring](#monitoring)
11. [Troubleshooting](#troubleshooting)

---

## 1. Prerequisites

### System Requirements
- **OS**: Ubuntu 20.04+ or RHEL 8+ (production), macOS/Windows (development)
- **CPU**: 8+ cores recommended
- **RAM**: 16GB minimum, 32GB recommended
- **Storage**: 100GB+ SSD
- **GPU**: NVIDIA GPU with 24GB+ VRAM for self-hosted LLM

### Software Requirements
```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Install Python 3.11+
sudo apt update
sudo apt install python3.11 python3.11-venv python3-pip

# Install AWS CLI
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Install Git
sudo apt install git
```

### GPU Setup (for self-hosted LLM)
```bash
# Install NVIDIA drivers
sudo apt install nvidia-driver-535

# Install NVIDIA Container Toolkit
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list
sudo apt update && sudo apt install -y nvidia-container-toolkit
sudo systemctl restart docker
```

---

## 2. Initial Setup

### Clone Repository
```bash
git clone https://github.com/your-org/hipaa-voice-agent.git
cd hipaa-voice-agent
```

### Create Environment File
```bash
cp config/.env.example config/.env
chmod 600 config/.env  # Restrict permissions
```

### Generate Encryption Keys
```bash
# Generate master encryption key
openssl rand -base64 32

# Generate data encryption key  
openssl rand -base64 32

# Generate JWT secret
openssl rand -hex 64

# Generate session secret
openssl rand -hex 32
```

Add these keys to your `.env` file:
```env
MASTER_ENCRYPTION_KEY=<your-master-key>
DATA_ENCRYPTION_KEY=<your-data-key>
JWT_SECRET=<your-jwt-secret>
SESSION_SECRET=<your-session-secret>
```

### Set Passwords
Generate strong passwords for:
```bash
# PostgreSQL
POSTGRES_PASSWORD=$(openssl rand -base64 24)

# Redis
REDIS_PASSWORD=$(openssl rand -base64 24)

# Temporal
TEMPORAL_DB_PASSWORD=$(openssl rand -base64 24)

# Grafana
GRAFANA_PASSWORD=$(openssl rand -base64 24)
```

---

## 3. Twilio Configuration

### Create HIPAA Project

1. **Sign BAA with Twilio**
   - Contact Twilio Sales for Enterprise account with BAA
   - Request HIPAA-eligible services activation

2. **Create HIPAA Project in Console**
   ```
   1. Log into Twilio Console
   2. Navigate to Settings > Projects
   3. Create New Project
   4. Select "HIPAA Eligible" option
   5. Name: "Medical Office Voice Agent"
   6. Save Project SID
   ```

3. **Purchase HIPAA-Eligible Phone Number**
   ```
   1. In HIPAA Project context
   2. Phone Numbers > Buy a Number
   3. Select number with Voice capability
   4. Configure Voice webhook
   ```

4. **Configure Webhooks**
   ```
   Voice URL: https://your-domain.com/webhooks/twilio/voice
   Method: POST
   Status Callback: https://your-domain.com/webhooks/twilio/status
   ```

5. **Enable Media Streams**
   - Ensure Media Streams is enabled for your project
   - This is required for real-time audio processing

6. **Update .env with Twilio Credentials**
   ```env
   TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   TWILIO_AUTH_TOKEN=your_auth_token
   TWILIO_API_KEY_SID=SKxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   TWILIO_API_KEY_SECRET=your_api_secret
   TWILIO_HIPAA_PROJECT_ID=PJxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   TWILIO_PHONE_NUMBER=+15025551234
   ```

---

## 4. AWS Configuration

### Create IAM User for Transcribe Medical

1. **Create IAM Policy**
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": [
           "transcribe:StartMedicalStreamTranscription",
           "transcribe:StartMedicalStreamTranscriptionWebSocket"
         ],
         "Resource": "*"
       },
       {
         "Effect": "Allow",
         "Action": [
           "s3:PutObject",
           "s3:GetObject",
           "s3:DeleteObject"
         ],
         "Resource": "arn:aws:s3:::hipaa-voice-recordings-encrypted/*"
       },
       {
         "Effect": "Allow",
         "Action": [
           "kms:Decrypt",
           "kms:GenerateDataKey"
         ],
         "Resource": "arn:aws:kms:us-east-1:*:key/*"
       }
     ]
   }
   ```

2. **Create IAM User**
   ```bash
   aws iam create-user --user-name hipaa-voice-agent
   aws iam attach-user-policy --user-name hipaa-voice-agent --policy-arn arn:aws:iam::aws:policy/AmazonTranscribeFullAccess
   aws iam create-access-key --user-name hipaa-voice-agent
   ```

3. **Create S3 Bucket with Encryption**
   ```bash
   # Create bucket
   aws s3api create-bucket --bucket hipaa-voice-recordings-encrypted \
     --region us-east-1 \
     --object-lock-enabled-for-bucket

   # Enable encryption
   aws s3api put-bucket-encryption --bucket hipaa-voice-recordings-encrypted \
     --server-side-encryption-configuration '{
       "Rules": [{
         "ApplyServerSideEncryptionByDefault": {
           "SSEAlgorithm": "aws:kms",
           "KMSMasterKeyID": "your-kms-key-id"
         }
       }]
     }'

   # Enable versioning
   aws s3api put-bucket-versioning --bucket hipaa-voice-recordings-encrypted \
     --versioning-configuration Status=Enabled
   ```

4. **Sign AWS BAA**
   - Log into AWS Console
   - Navigate to "My Account" > "AWS Artifact"
   - Accept the AWS Business Associate Addendum

5. **Update .env with AWS Credentials**
   ```env
   AWS_ACCESS_KEY_ID=AKIAXXXXXXXXXXXXXXXX
   AWS_SECRET_ACCESS_KEY=your_secret_key
   AWS_REGION=us-east-1
   AWS_S3_BUCKET=hipaa-voice-recordings-encrypted
   AWS_KMS_KEY_ID=arn:aws:kms:us-east-1:XXXXXXXXXXXX:key/XXXXXXXX
   ```

---

## 5. Self-Hosted LLM Setup

### Option A: Using vLLM with Llama 3

1. **Download Model**
   ```bash
   # Create models directory
   mkdir -p data/models

   # Download Llama 3 70B (requires access approval from Meta)
   # Follow instructions at: https://ai.meta.com/llama/
   ```

2. **Configure vLLM**
   ```env
   LLM_MODEL=meta-llama/Llama-3-70b-chat-hf
   LLM_ENDPOINT=http://vllm:8000/v1
   LLM_MAX_TOKENS=2048
   LLM_TEMPERATURE=0.7
   ```

### Option B: Using NVIDIA NIM

1. **Setup NVIDIA NIM**
   ```bash
   # Pull NIM container
   docker pull nvcr.io/nim/meta/llama3-70b-instruct:latest

   # Update docker-compose.yml to use NIM
   ```

2. **Configure NIM**
   ```env
   LLM_PROVIDER=nim
   LLM_ENDPOINT=http://nim:8000/v1
   NGC_API_KEY=your_ngc_api_key
   ```

---

## 6. FHIR Integration

### Connect to Your EHR System

#### Epic Integration
```env
FHIR_BASE_URL=https://your-epic-instance.com/FHIRProxy/api/FHIR/R4
FHIR_CLIENT_ID=your_epic_client_id
FHIR_CLIENT_SECRET=your_epic_client_secret
FHIR_AUTH_TYPE=oauth2
FHIR_TOKEN_ENDPOINT=https://your-epic-instance.com/FHIRProxy/oauth2/token
```

#### Cerner Integration
```env
FHIR_BASE_URL=https://fhir.cerner.com/r4/your-tenant-id
FHIR_CLIENT_ID=your_cerner_client_id
FHIR_CLIENT_SECRET=your_cerner_client_secret
FHIR_AUTH_TYPE=oauth2
FHIR_TOKEN_ENDPOINT=https://authorization.cerner.com/tenants/your-tenant-id/protocols/oauth2/profiles/smart-v1/token
```

#### Test FHIR Connection
```python
python scripts/test_fhir.py
```

---

## 7. Security Configuration

### Generate TLS Certificates

#### Production (Let's Encrypt)
```bash
# Install Certbot
sudo apt install certbot

# Generate certificates
sudo certbot certonly --standalone -d your-domain.com

# Copy certificates
sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem config/certs/server.crt
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem config/certs/server.key
sudo chmod 600 config/certs/server.key
```

#### Development (Self-Signed)
```bash
./scripts/generate-certs.sh development
```

### Configure Firewall
```bash
# Allow only necessary ports
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp  # SSH
sudo ufw allow 443/tcp # HTTPS
sudo ufw allow 8080/tcp # WebSocket (restrict source IPs in production)
sudo ufw enable
```

### Set File Permissions
```bash
# Secure configuration files
chmod 600 config/.env
chmod 600 config/certs/*

# Secure data directories
chmod 700 data/postgres
chmod 700 data/logs/audit
```

---

## 8. Deployment

### Production Deployment
```bash
# Run deployment script
./scripts/deploy.sh production

# This will:
# 1. Validate HIPAA compliance settings
# 2. Generate certificates
# 3. Start all services
# 4. Run compliance checks
# 5. Setup monitoring
```

### Verify Deployment
```bash
# Check service health
curl https://localhost:8080/health

# Check compliance
curl -H "Authorization: Bearer YOUR_API_KEY" https://localhost:8080/compliance

# View logs
docker-compose logs -f pipecat
```

---

## 9. Testing

### Run Test Suite
```bash
# Run all tests
python tests/test_agent.py

# Test specific components
python tests/test_agent.py TestPHIRedactor
python tests/test_agent.py TestHIPAACompliance
```

### Test Phone Call
```bash
# Make test call
./scripts/test-call.sh +15025551234

# Monitor WebSocket connection
docker-compose logs -f pipecat | grep WebSocket
```

### Load Testing
```bash
# Run load test (10 concurrent calls for 60 seconds)
./scripts/load-test.sh --concurrent=10 --duration=60
```

---

## 10. Monitoring

### Access Monitoring Dashboards

1. **Prometheus**: http://localhost:9090
   - Query metrics
   - Set up alerts

2. **Grafana**: http://localhost:3000
   - Default login: admin / [your-grafana-password]
   - Import dashboards from `config/grafana/dashboards/`

### Key Metrics to Monitor
- Call volume and duration
- ASR latency
- LLM response time
- Error rates
- System resources (CPU, memory, disk)
- Audit log volume

### Setup Alerts
```yaml
# config/prometheus/alerts.yml
groups:
  - name: hipaa_alerts
    rules:
      - alert: HighErrorRate
        expr: rate(errors_total[5m]) > 0.05
        for: 5m
        annotations:
          summary: High error rate detected
      
      - alert: LowDiskSpace
        expr: node_filesystem_avail_bytes{mountpoint="/"} < 10737418240
        for: 5m
        annotations:
          summary: Less than 10GB disk space remaining
```

---

## 11. Troubleshooting

### Common Issues

#### WebSocket Connection Fails
```bash
# Check Twilio webhook configuration
curl -X POST https://your-domain.com/webhooks/twilio/voice

# Verify certificates
openssl s_client -connect your-domain.com:8080

# Check firewall rules
sudo ufw status
```

#### ASR Not Working
```bash
# Test AWS credentials
aws transcribe list-medical-transcription-jobs

# Check network connectivity
docker exec hipaa-pipecat ping transcribe.us-east-1.amazonaws.com
```

#### LLM Timeout
```bash
# Check vLLM status
docker logs hipaa-llm

# Test LLM endpoint
curl http://localhost:8000/v1/models

# Increase timeout in .env
LLM_TIMEOUT=60
```

#### Database Connection Issues
```bash
# Check PostgreSQL
docker exec hipaa-postgres pg_isready

# Reset database
docker-compose down -v
docker-compose up -d postgres
```

### Debug Mode
```env
# Enable debug logging
DEBUG=true
LOG_LEVEL=DEBUG
VERBOSE_ERRORS=true
```

### Support Contacts
- Technical Issues: tech-support@your-org.com
- Compliance Questions: compliance@your-org.com
- Emergency On-Call: +1-502-555-0911

---

## 📝 Compliance Checklist

Before going live, ensure:

- [ ] BAAs signed with Twilio, AWS, and all vendors
- [ ] TLS certificates installed and valid
- [ ] Encryption keys generated and secured
- [ ] Audit logging enabled with 7-year retention
- [ ] PHI redaction enabled
- [ ] Backups configured with encryption
- [ ] Firewall rules configured
- [ ] Staff HIPAA training completed
- [ ] Incident response plan documented
- [ ] Disaster recovery plan tested
- [ ] Compliance audit passed (run `./scripts/compliance-audit.sh`)

---

## 🔄 Regular Maintenance

### Daily Tasks
- Review audit logs
- Check system health
- Monitor error rates

### Weekly Tasks
- Run compliance audit
- Review call analytics
- Update documentation

### Monthly Tasks
- Rotate API keys
- Update dependencies
- Security patches
- Test disaster recovery

### Quarterly Tasks
- Full security audit
- HIPAA training refresh
- Performance optimization
- Capacity planning

---

## 📚 Additional Resources

- [HIPAA Security Rule](https://www.hhs.gov/hipaa/for-professionals/security/index.html)
- [Twilio HIPAA Docs](https://www.twilio.com/docs/voice/tutorials/hipaa-compliant-call-center)
- [AWS HIPAA Guide](https://docs.aws.amazon.com/whitepapers/latest/architecting-hipaa-security-and-compliance-on-aws/welcome.html)
- [FHIR R4 Specification](https://www.hl7.org/fhir/R4/)
- [Pipecat Documentation](https://github.com/pipecat-ai/pipecat)

---

**Last Updated**: January 2024  
**Version**: 1.0.0  
**Maintained By**: Your Organization DevOps Team
