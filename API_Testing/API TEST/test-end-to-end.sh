#!/bin/bash

# End-to-End ERI Integration Testing
# Tests complete hybrid architecture flow

echo "=========================================="
echo "End-to-End ERI Integration Testing"
echo "Hybrid Architecture: Local DSC + AWS ERI"
echo "=========================================="

LOCAL_SIGNER_URL="http://localhost:9090"
AWS_BACKEND_URL="http://13.204.49.125:8080"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test Results Tracking
TESTS_PASSED=0
TESTS_FAILED=0
TOTAL_TESTS=0

# Function to run test and track results
run_test() {
    local test_name="$1"
    local test_command="$2"
    local expected_result="$3"
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    echo -e "\n${BLUE}Test $TOTAL_TESTS: $test_name${NC}"
    echo "Command: $test_command"
    
    if eval "$test_command"; then
        echo -e "${GREEN}✓ PASSED: $test_name${NC}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        echo -e "${RED}✗ FAILED: $test_name${NC}"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

# Pre-flight Checks
echo -e "\n${YELLOW}=== PRE-FLIGHT CHECKS ===${NC}"

# Check 1: Local DSC Signer Health
run_test "Local DSC Signer Health" \
    "curl -s -f $LOCAL_SIGNER_URL/api/health > /dev/null" \
    "HTTP 200"

if [ $? -ne 0 ]; then
    echo -e "${RED}CRITICAL: Local DSC signer not available${NC}"
    echo "Start local signer: java -jar -Dspring.profiles.active=local target/eri-tax-erp-phase1-1.0.0-SNAPSHOT.jar"
    exit 1
fi

# Check 2: AWS Backend Health
run_test "AWS Backend Health" \
    "curl -s -f $AWS_BACKEND_URL/api/health > /dev/null" \
    "HTTP 200"

if [ $? -ne 0 ]; then
    echo -e "${RED}CRITICAL: AWS backend not available${NC}"
    echo "Check AWS EC2 service status and network connectivity"
    exit 1
fi

# Check 3: USB Token Status
echo -e "\n${YELLOW}Checking USB DSC Token Status...${NC}"
TOKEN_STATUS=$(curl -s "$LOCAL_SIGNER_URL/api/token/status")
TOKEN_AVAILABLE=$(echo "$TOKEN_STATUS" | jq -r '.available // false')

if [ "$TOKEN_AVAILABLE" = "true" ]; then
    echo -e "${GREEN}✓ USB DSC Token Available${NC}"
    echo "$TOKEN_STATUS" | jq '.certificate'
else
    echo -e "${RED}✗ USB DSC Token Not Available${NC}"
    echo "$TOKEN_STATUS" | jq '.message'
    echo -e "${YELLOW}Insert USB token and check PIN configuration${NC}"
    exit 1
fi

# Main Test Scenarios
echo -e "\n${YELLOW}=== MAIN TEST SCENARIOS ===${NC}"

# Scenario 1: Complete ERI Login Flow
echo -e "\n${BLUE}Scenario 1: Complete ERI Login Flow${NC}"

# Step 1: Generate login payload
ERI_LOGIN_PAYLOAD='{
  "userId": "ERIP013181",
  "password": "Oracle@123",
  "eriUserId": "ERIP011535",
  "timestamp": "'$(date -u +"%Y-%m-%dT%H:%M:%S")'",
  "action": "LOGIN",
  "clientId": "4fea04621c7b5660dbb12b959a29b0ee",
  "sessionType": "UAT_TESTING"
}'

echo "Step 1: Generating canonical JSON payload..."
CANONICAL_PAYLOAD=$(echo "$ERI_LOGIN_PAYLOAD" | jq -c .)
echo "Payload: $CANONICAL_PAYLOAD"

# Step 2: Sign payload locally
echo -e "\nStep 2: Signing payload with local DSC..."
SIGNING_RESPONSE=$(curl -s -X POST \
  -H "Content-Type: application/json" \
  -d "{\"payload\":$CANONICAL_PAYLOAD}" \
  "$LOCAL_SIGNER_URL/api/sign")

echo "Signing Response:"
echo "$SIGNING_RESPONSE" | jq '.'

SIGNING_SUCCESS=$(echo "$SIGNING_RESPONSE" | jq -r '.success // false')
SIGNED_DATA=$(echo "$SIGNING_RESPONSE" | jq -r '.data // empty')
SIGNATURE=$(echo "$SIGNING_RESPONSE" | jq -r '.signature // empty')

if [ "$SIGNING_SUCCESS" = "true" ]; then
    echo -e "${GREEN}✓ Local DSC signing successful${NC}"
    echo "Data length: ${#SIGNED_DATA} chars"
    echo "Signature length: ${#SIGNATURE} chars"
else
    echo -e "${RED}✗ Local DSC signing failed${NC}"
    exit 1
fi

# Step 3: Send to AWS backend
echo -e "\nStep 3: Sending signed payload to AWS backend..."
AWS_REQUEST='{
  "data": "'$SIGNED_DATA'",
  "signature": "'$SIGNATURE'",
  "eriUserId": "ERIP011535"
}'

AWS_RESPONSE=$(curl -s -w "\nHTTP_STATUS:%{http_code}\nRESPONSE_TIME:%{time_total}" \
  -X POST \
  -H "Content-Type: application/json" \
  -H "X-Test-Scenario: end-to-end-login" \
  -d "$AWS_REQUEST" \
  "$AWS_BACKEND_URL/api/eri/login-signed")

# Parse AWS response
HTTP_STATUS=$(echo "$AWS_RESPONSE" | grep "HTTP_STATUS:" | cut -d: -f2)
RESPONSE_TIME=$(echo "$AWS_RESPONSE" | grep "RESPONSE_TIME:" | cut -d: -f2)
JSON_RESPONSE=$(echo "$AWS_RESPONSE" | sed '/HTTP_STATUS:/d' | sed '/RESPONSE_TIME:/d')

echo "AWS Response:"
echo "$JSON_RESPONSE" | jq '.'
echo "HTTP Status: $HTTP_STATUS"
echo "Response Time: ${RESPONSE_TIME}s"

# Step 4: Validate ERI login result
LOGIN_SUCCESS=$(echo "$JSON_RESPONSE" | jq -r '.success // false')
SESSION_ID=$(echo "$JSON_RESPONSE" | jq -r '.sessionId // empty')

if [ "$LOGIN_SUCCESS" = "true" ] && [ -n "$SESSION_ID" ]; then
    echo -e "${GREEN}✓ ERI login successful - Session ID: $SESSION_ID${NC}"
    TESTS_PASSED=$((TESTS_PASSED + 1))
    
    # Scenario 2: Session Management
    echo -e "\n${BLUE}Scenario 2: Session Management${NC}"
    
    # Session status check
    echo "Checking session status..."
    SESSION_STATUS=$(curl -s "$AWS_BACKEND_URL/api/eri/session/$SESSION_ID/status")
    echo "$SESSION_STATUS" | jq '.'
    
    SESSION_VALID=$(echo "$SESSION_STATUS" | jq -r '.valid // false')
    if [ "$SESSION_VALID" = "true" ]; then
        echo -e "${GREEN}✓ Session is valid and active${NC}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo -e "${RED}✗ Session validation failed${NC}"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
    
    # Logout
    echo -e "\nLogging out..."
    LOGOUT_RESPONSE=$(curl -s -X POST \
      -H "Content-Type: application/json" \
      -d "{\"sessionId\":\"$SESSION_ID\"}" \
      "$AWS_BACKEND_URL/api/eri/logout")
    
    echo "$LOGOUT_RESPONSE" | jq '.'
    
    LOGOUT_SUCCESS=$(echo "$LOGOUT_RESPONSE" | jq -r '.success // false')
    if [ "$LOGOUT_SUCCESS" = "true" ]; then
        echo -e "${GREEN}✓ Logout successful${NC}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo -e "${RED}✗ Logout failed${NC}"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
    
else
    echo -e "${RED}✗ ERI login failed${NC}"
    ERROR_MSG=$(echo "$JSON_RESPONSE" | jq -r '.error // "Unknown error"')
    ERROR_CODE=$(echo "$JSON_RESPONSE" | jq -r '.errorCode // "UNKNOWN"')
    echo "Error: $ERROR_MSG"
    echo "Error Code: $ERROR_CODE"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

TOTAL_TESTS=$((TOTAL_TESTS + 4)) # Login, Session Check, Logout, Overall Flow

# Scenario 3: Error Handling Tests
echo -e "\n${BLUE}Scenario 3: Error Handling Tests${NC}"

# Test invalid payload
echo "Testing invalid payload handling..."
INVALID_RESPONSE=$(curl -s -X POST \
  -H "Content-Type: application/json" \
  -d '{"data":"invalid","signature":"invalid","eriUserId":"ERIP011535"}' \
  "$AWS_BACKEND_URL/api/eri/login-signed")

INVALID_SUCCESS=$(echo "$INVALID_RESPONSE" | jq -r '.success // true')
if [ "$INVALID_SUCCESS" = "false" ]; then
    echo -e "${GREEN}✓ Invalid payload properly rejected${NC}"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}✗ Invalid payload not properly handled${NC}"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

TOTAL_TESTS=$((TOTAL_TESTS + 1))

# Scenario 4: Performance Testing
echo -e "\n${BLUE}Scenario 4: Performance Testing${NC}"

echo "Testing signing performance (5 iterations)..."
TOTAL_SIGN_TIME=0
SUCCESSFUL_SIGNS=0

for i in {1..5}; do
    START_TIME=$(date +%s%N)
    
    PERF_PAYLOAD='{"test":true,"iteration":'$i',"timestamp":"'$(date -u +"%Y-%m-%dT%H:%M:%S")'"}'
    
    PERF_RESPONSE=$(curl -s -X POST \
      -H "Content-Type: application/json" \
      -d "{\"payload\":$PERF_PAYLOAD}" \
      "$LOCAL_SIGNER_URL/api/sign")
    
    END_TIME=$(date +%s%N)
    ITERATION_TIME=$(( (END_TIME - START_TIME) / 1000000 )) # Convert to milliseconds
    
    PERF_SUCCESS=$(echo "$PERF_RESPONSE" | jq -r '.success // false')
    if [ "$PERF_SUCCESS" = "true" ]; then
        SUCCESSFUL_SIGNS=$((SUCCESSFUL_SIGNS + 1))
        TOTAL_SIGN_TIME=$((TOTAL_SIGN_TIME + ITERATION_TIME))
        echo "  Iteration $i: ${ITERATION_TIME}ms"
    else
        echo "  Iteration $i: FAILED"
    fi
done

if [ $SUCCESSFUL_SIGNS -gt 0 ]; then
    AVERAGE_TIME=$((TOTAL_SIGN_TIME / SUCCESSFUL_SIGNS))
    echo "Average signing time: ${AVERAGE_TIME}ms ($SUCCESSFUL_SIGNS/5 successful)"
    
    if [ $AVERAGE_TIME -lt 5000 ]; then
        echo -e "${GREEN}✓ Performance acceptable (< 5s average)${NC}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo -e "${YELLOW}⚠ Performance slow (> 5s average)${NC}"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
else
    echo -e "${RED}✗ All performance tests failed${NC}"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

TOTAL_TESTS=$((TOTAL_TESTS + 1))

# Final Results
echo -e "\n=========================================="
echo -e "${YELLOW}END-TO-END TESTING RESULTS${NC}"
echo "=========================================="

echo "Total Tests: $TOTAL_TESTS"
echo -e "Passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "Failed: ${RED}$TESTS_FAILED${NC}"

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "\n${GREEN}🎉 ALL TESTS PASSED! 🎉${NC}"
    echo -e "${GREEN}Hybrid ERI integration is working correctly${NC}"
    
    echo -e "\n${YELLOW}SYSTEM READY FOR PRODUCTION UAT${NC}"
    echo "✓ Local DSC signing operational"
    echo "✓ AWS backend operational"
    echo "✓ ERI API integration working"
    echo "✓ Session management working"
    echo "✓ Error handling working"
    echo "✓ Performance acceptable"
    
else
    echo -e "\n${RED}❌ SOME TESTS FAILED ❌${NC}"
    echo -e "${RED}Fix issues before proceeding to production${NC}"
    
    echo -e "\n${YELLOW}TROUBLESHOOTING CHECKLIST:${NC}"
    echo "1. Check USB DSC token insertion and PIN"
    echo "2. Verify VPN connection to ITD network"
    echo "3. Confirm IP whitelisting status (24-48hr delay)"
    echo "4. Check ERI credentials configuration"
    echo "5. Verify AWS EC2 service status"
    echo "6. Check network connectivity between components"
fi

echo -e "\n${YELLOW}COMPONENT STATUS:${NC}"
echo "Local DSC Signer: $LOCAL_SIGNER_URL"
echo "AWS Backend: $AWS_BACKEND_URL"
echo "ERI API: https://uatocpservices.incometax.gov.in/v1"

echo -e "\n${YELLOW}NEXT STEPS:${NC}"
if [ $TESTS_FAILED -eq 0 ]; then
    echo "1. System is ready for production UAT testing"
    echo "2. Begin actual tax return processing"
    echo "3. Monitor audit logs and performance"
else
    echo "1. Fix failing tests"
    echo "2. Re-run end-to-end testing"
    echo "3. Contact support if issues persist"
fi

# Exit with appropriate code
exit $TESTS_FAILED