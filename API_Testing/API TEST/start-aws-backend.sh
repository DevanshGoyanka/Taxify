#!/bin/bash

# Start AWS ERI Backend Service
# Runs on AWS EC2 with whitelisted IP

echo "========================================"
echo "AWS ERI Backend Service"
echo "Port: 8080"
echo "IP: 13.204.49.125"
echo "========================================"

# Set environment variables
export ERI_CLIENT_ID=4fea04621c7b5660dbb12b959a29b0ee
export ERI_CLIENT_SECRET=e754ceb48732c4e197658f76bcc69037
export ERI_USERNAME=ERIP013181
export ERI_PASSWORD=Oracle@123
export ERI_USER_ID=ERIP011535
export DB_USERNAME=taxerp_user
export DB_PASSWORD=${DB_PASSWORD:-your_db_password}
export LOCAL_SIGNER_URL=${LOCAL_SIGNER_URL:-http://localhost:9090}

echo ""
echo "Configuration:"
echo "  ERI Base URL: https://uatocpservices.incometax.gov.in/v1"
echo "  Local Signer: $LOCAL_SIGNER_URL"
echo "  Database: taxerp_uat"
echo ""

# Check database
echo "Checking database connectivity..."
mysql -h localhost -u $DB_USERNAME -p$DB_PASSWORD -e "SELECT 1;" taxerp_uat 2>/dev/null
if [ $? -eq 0 ]; then
    echo "✓ Database connection successful"
else
    echo "✗ Database connection failed"
    echo "Please check database configuration"
    exit 1
fi

# Create logs directory
mkdir -p logs

echo ""
echo "Starting AWS ERI Backend Service..."
java -jar -Dspring.profiles.active=aws target/eri-tax-erp-phase1-1.0.0-SNAPSHOT.jar

echo "AWS Backend service stopped"
