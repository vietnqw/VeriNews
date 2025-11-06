#!/bin/bash
# Check application health

set -e

echo "======================================"
echo "VeriNews Health Check"
echo "======================================"

BASE_URL="http://localhost:8000"

echo ""
echo "Checking root endpoint..."
curl -s "$BASE_URL/" | python3 -m json.tool

echo ""
echo "Checking simple health..."
curl -s "$BASE_URL/api/v1/health/simple" | python3 -m json.tool

echo ""
echo "Checking full health (with database)..."
curl -s "$BASE_URL/api/v1/health" | python3 -m json.tool

echo ""
echo "======================================"
echo "✅ Health check complete"
echo "======================================"
