#!/bin/bash

# Test Local DSC Signing Service
# Tests USB DSC token signing functionality on Windows laptop

echo "=========================================="
echo "Testing Local DSC Signing Service"
echo "Port: 9090"
echo "=========================================="

LOCAL_SIGNER_URL="http://localhost:9090"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test 1: Health Check
echo -e "\n${YELLOW}Test 1: Health Check${NC}"
echo "GET $LOCAL_SIGNER_URL/api/health"

curl -s -w "\nHTTP Status: %{http_code}\nResponse Time: %{time_total}s\n" \
  -H "Content-Type: application/json" \
  "$LOCAL_SIGNER_URL/api/health" | jq '.'

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Health check passed${NC}"
else
    echo -e "${RED}✗ Health check failed${NC}"
fi

# Test 2: Token Status
echo -e "\n${YELLOW}Test 2: USB Token Status${NC}"
echo "GET $LOCAL_SIGNER_URL/api/token/status"

curl -s -w "\nHTTP Status: %{http_code}\n" \
  -H "Content-Type: application/json" \
  "$LOCAL_SIGNER_URL/api/token/status" | jq '.'

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Token status check completed${NC}"
else
    echo -e "${RED}✗ Token status check failed${NC}"
fi

# Test 3: Service Info
echo -e "\n${YELLOW}Test 3: Service Information${NC}"
echo "GET $LOCAL_SIGNER_URL/api/info"

curl -s -w "\nHTTP Status: %{http_code}\n" \
  -H "Content-Type: application/json" \
  "$LOCAL_SIGNER_URL/api/info" | jq '.'

# Test 4: Simple Signing Test
echo -e "\n${YELLOW}Test 4: Simple Signing Test${NC}"
echo "POST $LOCAL_SIGNER_URL/api/sign"

TEST_PAYLOAD='{"message":"Hello ITD ERI UAT","timestamp":"2024-01-15T10:30:00","test":true}'

curl -s -w "\nHTTP Status: %{http_code}\nResponse Time: %{time_total}s\n" \
  -X POST \
  -H "Content-Type: application/json" \
  -d "{\"payload\":\"$TEST_PAYLOAD\"}" \
  "$LOCAL_SIGNER_URL/api/sign" | jq '.'

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Simple signing test completed${NC}"
else
    echo -e "${RED}✗ Simple signing test failed${NC}"
fi

# Test 5: ERI Login Payload Signing
echo -e "\n${YELLOW}Test 5: ERI Login Payload Signing${NC}"
echo "POST $LOCAL_SIGNER_URL/api/sign"

ERI_LOGIN_PAYLOAD='{
  "userId": "ERIP013181",
  "password": "Oracle@123",
  "eriUserId": "ERIP011535",
  "timestamp": "'$(date -u +"%Y-%m-%dT%H:%M:%S")'",
  "action": "LOGIN"
}'

curl -s -w "\nHTTP Status: %{http_code}\nResponse Time: %{time_total}s\n" \
  -X POST \
  -H "Content-Type: application/json" \
  -d "{\"payload\":$(echo "$ERI_LOGIN_PAYLOAD" | jq -c .)}" \
  "$LOCAL_SIGNER_URL/api/sign" | jq '.'

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ ERI login payload signing completed${NC}"
else
    echo -e "${RED}✗ ERI login payload signing failed${NC}"
fi

# Test 6: Large Payload Signing
echo -e "\n${YELLOW}Test 6: Large Payload Signing${NC}"
echo "POST $LOCAL_SIGNER_URL/api/sign"

LARGE_PAYLOAD='{
  "formData": {
    "assessmentYear": "2024-25",
    "panNumber": "ABCDE1234F",
    "returnType": "ITR-1",
    "filingDate": "2024-07-31",
    "totalIncome": 500000,
    "taxPayable": 12500,
    "sections": {
      "salaryIncome": 450000,
      "housePropertyIncome": 50000,
      "otherSources": 0,
      "deductions": {
        "section80C": 150000,
        "section80D": 25000
      }
    }
  },
  "submissionType": "ORIGINAL",
  "acknowledgmentNumber": "TEST'$(date +%s)'",
  "timestamp": "'$(date -u +"%Y-%m-%dT%H:%M:%S")'"
}'

curl -s -w "\nHTTP Status: %{http_code}\nResponse Time: %{time_total}s\n" \
  -X POST \
  -H "Content-Type: application/json" \
  -d "{\"payload\":$(echo "$LARGE_PAYLOAD" | jq -c .)}" \
  "$LOCAL_SIGNER_URL/api/sign" | jq '.'

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Large payload signing completed${NC}"
else
    echo -e "${RED}✗ Large payload signing failed${NC}"
fi

# Test 7: Error Handling - Invalid Payload
echo -e "\n${YELLOW}Test 7: Error Handling - Missing Payload${NC}"
echo "POST $LOCAL_SIGNER_URL/api/sign"

curl -s -w "\nHTTP Status: %{http_code}\n" \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{}' \
  "$LOCAL_SIGNER_URL/api/sign" | jq '.'

echo -e "${YELLOW}Expected: HTTP 400 with error message${NC}"

# Test 8: Error Handling - Malformed JSON
echo -e "\n${YELLOW}Test 8: Error Handling - Malformed JSON${NC}"
echo "POST $LOCAL_SIGNER_URL/api/sign"

curl -s -w "\nHTTP Status: %{http_code}\n" \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"payload":' \
  "$LOCAL_SIGNER_URL/api/sign"

echo -e "${YELLOW}Expected: HTTP 400 with JSON parsing error${NC}"

echo -e "\n=========================================="
echo -e "${GREEN}Local DSC Signer Testing Complete${NC}"
echo "=========================================="

# Summary
echo -e "\n${YELLOW}TROUBLESHOOTING GUIDE:${NC}"
echo "1. If health check fails: Check if service is running on port 9090"
echo "2. If token status fails: Check USB token insertion and drivers"
echo "3. If signing fails: Check PIN configuration (DSC_PASSWORD env var)"
echo "4. If PKCS#11 errors: Check eps2003csp11v2.dll in System32"
echo "5. If certificate errors: Check certificate alias configuration"

echo -e "\n${YELLOW}NEXT STEPS:${NC}"
echo "1. If all tests pass: Proceed to test AWS backend"
echo "2. If tests fail: Fix issues before proceeding"
echo "3. Run: ./test-aws-backend.sh"