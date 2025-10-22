#!/bin/bash
# Quick Start Script - RCM Platform
# Automates initial setup

set -e

echo "🚀 RCM Platform - Quick Start"
echo "=============================="
echo ""

# Check prerequisites
echo "Checking prerequisites..."

if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Install: https://docs.docker.com/get-docker/"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose not found. Install: https://docs.docker.com/compose/install/"
    exit 1
fi

if ! command -v node &> /dev/null; then
    echo "❌ Node.js not found. Install: https://nodejs.org/"
    exit 1
fi

echo "✅ All prerequisites installed"
echo ""

# Step 1: Environment setup
if [ ! -f .env ]; then
    echo "📝 Creating .env file..."
    cp .env.example .env
    echo "✅ Created .env file"
    echo "⚠️  IMPORTANT: Edit .env and add your API keys:"
    echo "   - STEDI_API_KEY"
    echo "   - CLOUDFLARE_ACCOUNT_ID"
    echo "   - CLOUDFLARE_API_TOKEN"
    echo ""
    read -p "Press Enter after you've added API keys..."
fi

# Step 2: Start backend services
echo "🐳 Starting backend services (Docker)..."
docker-compose up -d

echo "⏳ Waiting for services to be healthy (30s)..."
sleep 30

# Check health
echo "🏥 Checking service health..."
if curl -s http://localhost:8000/health | grep -q "healthy"; then
    echo "✅ Backend API is healthy"
else
    echo "❌ Backend API not responding. Check logs:"
    echo "   docker-compose logs api"
    exit 1
fi

# Step 3: Deploy Cloudflare Worker (if not already deployed)
echo ""
echo "☁️  Deploying Cloudflare Worker..."
cd workers

if ! command -v wrangler &> /dev/null; then
    echo "📦 Installing Wrangler CLI..."
    npm install -g wrangler
fi

echo "🔐 Logging into Cloudflare..."
wrangler login

echo "🚀 Deploying AI claim scrubber..."
wrangler deploy

echo "✅ Worker deployed!"
echo "⚠️  Copy the worker URL and add to .env:"
echo "   CLOUDFLARE_WORKER_URL=https://claim-scrubber.XXXXX.workers.dev"
echo ""
read -p "Press Enter after updating .env..."

cd ..

# Step 4: Frontend (optional - can deploy later)
echo ""
read -p "Deploy frontend to Cloudflare Pages? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🎨 Building and deploying frontend..."
    cd frontend

    if [ ! -d "node_modules" ]; then
        echo "📦 Installing frontend dependencies..."
        npm install
    fi

    echo "🏗️  Building frontend..."
    npm run build

    echo "☁️  Deploying to Cloudflare Pages..."
    npm run deploy

    echo "✅ Frontend deployed!"
    cd ..
fi

# Step 5: Summary
echo ""
echo "✅ Setup Complete!"
echo "=================="
echo ""
echo "🎉 Your RCM Platform is live!"
echo ""
echo "📍 Access Points:"
echo "  - Backend API: http://localhost:8000"
echo "  - API Docs: http://localhost:8000/docs"
echo "  - Health Check: http://localhost:8000/health"
echo "  - Medplum: http://localhost:8103"
echo ""
echo "🧪 Test Endpoints:"
echo "  curl http://localhost:8000/health"
echo "  curl -X POST http://localhost:8000/api/eligibility/check \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"patient_id\":\"test\",\"provider_npi\":\"1234567890\"}'"
echo ""
echo "📖 Next Steps:"
echo "  1. Create test patient in Medplum (see README.md)"
echo "  2. Test eligibility check"
echo "  3. Test AI claim scrubber"
echo "  4. Contact physician family members"
echo "  5. Schedule demos for Friday"
echo ""
echo "🚀 Week 1 Goal: 10 pilot commitments!"
echo ""
