#!/bin/bash

# Test AWS Backend ERI Integration
# Tests signed payload acceptance and ERI API calls from AWS EC2

echo "=========================================="
echo "Testing AWS Backend ERI Integration"
echo "AWS IP: 13.204.49.125:8080"
echo "=========================================="

AWS_BACKEND_URL="http://13.204.49.125:8080"
LOCAL_SIGNER_URL="http://localhost:9090"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test 1: AWS Backend Health Check
echo -e "\n${YELLOW}Test 1: AWS Backend Health Check${NC}"
echo "GET $AWS_BACKEND_URL/api/health"

curl -s -w "\nHTTP Status: %{http_code}\nResponse Time: %{time_total}s\n" \
  -H "Content-Type: application/json" \
  "$AWS_BACKEND_URL/api/health" | jq '.'

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ AWS backend health check passed${NC}"
else
    echo -e "${RED}✗ AWS backend health check failed${NC}"
    echo -e "${RED}Cannot proceed without AWS backend${NC}"
    exit 1
fi

# Test 2: Generate Signed Payload Locally
echo -e "\n${YELLOW}Test 2: Generate Signed Payload (Local DSC)${NC}"
echo "POST $LOCAL_SIGNER_URL/api/sign"

ERI_LOGIN_PAYLOAD='{
  "userId": "ERIP013181",
  "password": "Oracle@123",
  "eriUserId": "ERIP011535",
  "timestamp": "'$(date -u +"%Y-%m-%dT%H:%M:%S")'",
  "action": "LOGIN",
  "clientId": "4fea04621c7b5660dbb12b959a29b0ee"
}'

echo "Generating signed payload..."
SIGNING_RESPONSE=$(curl -s -X POST \
  -H "Content-Type: application/json" \
  -d "{\"payload\":$(echo "$ERI_LOGIN_PAYLOAD" | jq -c .)}" \
  "$LOCAL_SIGNER_URL/api/sign")

echo "$SIGNING_RESPONSE" | jq '.'

# Extract data and signature
SIGNED_DATA=$(echo "$SIGNING_RESPONSE" | jq -r '.data // empty')
SIGNATURE=$(echo "$SIGNING_RESPONSE" | jq -r '.signature // empty')
SIGNING_SUCCESS=$(echo "$SIGNING_RESPONSE" | jq -r '.success // false')

if [ "$SIGNING_SUCCESS" = "true" ] && [ -n "$SIGNED_DATA" ] && [ -n "$SIGNATURE" ]; then
    echo -e "${GREEN}✓ Local signing successful${NC}"
    echo "Data length: ${#SIGNED_DATA}"
    echo "Signature length: ${#SIGNATURE}"
else
    echo -e "${RED}✗ Local signing failed${NC}"
    echo "Cannot proceed without signed payload"
    exit 1
fi

# Test 3: Send Signed Payload to AWS Backend
echo -e "\n${YELLOW}Test 3: Send Signed Payload to AWS Backend${NC}"
echo "POST $AWS_BACKEND_URL/api/eri/login-signed"

AWS_REQUEST='{
  "data": "'$SIGNED_DATA'",
  "signature": "'$SIGNATURE'",
  "eriUserId": "ERIP011535"
}'

echo "Sending signed payload to AWS..."
AWS_RESPONSE=$(curl -s -w "\nHTTP_STATUS:%{http_code}\nRESPONSE_TIME:%{time_total}" \
  -X POST \
  -H "Content-Type: application/json" \
  -d "$AWS_REQUEST" \
  "$AWS_BACKEND_URL/api/eri/login-signed")

# Parse response
HTTP_STATUS=$(echo "$AWS_RESPONSE" | grep "HTTP_STATUS:" | cut -d: -f2)
RESPONSE_TIME=$(echo "$AWS_RESPONSE" | grep "RESPONSE_TIME:" | cut -d: -f2)
JSON_RESPONSE=$(echo "$AWS_RESPONSE" | sed '/HTTP_STATUS:/d' | sed '/RESPONSE_TIME:/d')

echo "$JSON_RESPONSE" | jq '.'
echo "HTTP Status: $HTTP_STATUS"
echo "Response Time: ${RESPONSE_TIME}s"

# Check if login was successful
LOGIN_SUCCESS=$(echo "$JSON_RESPONSE" | jq -r '.success // false')
SESSION_ID=$(echo "$JSON_RESPONSE" | jq -r '.sessionId // empty')

if [ "$LOGIN_SUCCESS" = "true" ] && [ -n "$SESSION_ID" ]; then
    echo -e "${GREEN}✓ ERI login successful${NC}"
    echo "Session ID: $SESSION_ID"
    
    # Test 4: Session Status Check
    echo -e "\n${YELLOW}Test 4: Session Status Check${NC}"
    echo "GET $AWS_BACKEND_URL/api/eri/session/$SESSION_ID/status"
    
    curl -s -w "\nHTTP Status: %{http_code}\n" \
      -H "Content-Type: application/json" \
      "$AWS_BACKEND_URL/api/eri/session/$SESSION_ID/status" | jq '.'
    
    # Test 5: Logout
    echo -e "\n${YELLOW}Test 5: ERI Logout${NC}"
    echo "POST $AWS_BACKEND_URL/api/eri/logout"
    
    curl -s -w "\nHTTP Status: %{http_code}\n" \
      -X POST \
      -H "Content-Type: application/json" \
      -d "{\"sessionId\":\"$SESSION_ID\"}" \
      "$AWS_BACKEND_URL/api/eri/logout" | jq '.'
    
else
    echo -e "${RED}✗ ERI login failed${NC}"
    ERROR_MSG=$(echo "$JSON_RESPONSE" | jq -r '.error // "Unknown error"')
    ERROR_CODE=$(echo "$JSON_RESPONSE" | jq -r '.errorCode // "UNKNOWN"')
    echo "Error: $ERROR_MSG"
    echo "Error Code: $ERROR_CODE"
fi

# Test 6: Error Handling - Invalid Signature
echo -e "\n${YELLOW}Test 6: Error Handling - Invalid Signature${NC}"
echo "POST $AWS_BACKEND_URL/api/eri/login-signed"

INVALID_REQUEST='{
  "data": "'$SIGNED_DATA'",
  "signature": "INVALID_SIGNATURE_BASE64",
  "eriUserId": "ERIP011535"
}'

curl -s -w "\nHTTP Status: %{http_code}\n" \
  -X POST \
  -H "Content-Type: application/json" \
  -d "$INVALID_REQUEST" \
  "$AWS_BACKEND_URL/api/eri/login-signed" | jq '.'

echo -e "${YELLOW}Expected: HTTP 400 with validation error${NC}"

# Test 7: Error Handling - Missing Fields
echo -e "\n${YELLOW}Test 7: Error Handling - Missing Fields${NC}"
echo "POST $AWS_BACKEND_URL/api/eri/login-signed"

curl -s -w "\nHTTP Status: %{http_code}\n" \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"data":"test"}' \
  "$AWS_BACKEND_URL/api/eri/login-signed" | jq '.'

echo -e "${YELLOW}Expected: HTTP 400 with missing fields error${NC}"

echo -e "\n=========================================="
echo -e "${GREEN}AWS Backend Testing Complete${NC}"
echo "=========================================="

# Summary
echo -e "\n${YELLOW}TROUBLESHOOTING GUIDE:${NC}"
echo "1. If AWS health fails: Check AWS EC2 service status"
echo "2. If connection refused: Check VPN and network connectivity"
echo "3. If ERI login fails: Check IP whitelisting status (24-48hr delay)"
echo "4. If unauthorized: Check ERI credentials configuration"
echo "5. If signature invalid: Check local DSC signing service"

echo -e "\n${YELLOW}NEXT STEPS:${NC}"
echo "1. If all tests pass: Proceed to end-to-end testing"
echo "2. If ERI login fails: Check VPN and IP whitelisting"
echo "3. Run: ./test-end-to-end.sh"