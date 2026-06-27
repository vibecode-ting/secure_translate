#!/bin/bash
# Secure Translate - API Test Suite
# Tests all endpoints to verify the app works correctly

BASE_URL="http://localhost:8000"
PASS=0
FAIL=0
DOCUMENT_ID=""
REGION_IDS=""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

test_pass() {
    echo -e "  ${GREEN}✅ PASS${NC}: $1"
    ((PASS++))
}

test_fail() {
    echo -e "  ${RED}❌ FAIL${NC}: $1"
    ((FAIL++))
}

echo "========================================"
echo "  Secure Translate - API Test Suite"
echo "========================================"
echo ""

# --- Test 1: Health Check ---
echo -e "${YELLOW}Test 1: Health Check${NC}"
RESPONSE=$(curl -s "$BASE_URL/api/health")
if echo "$RESPONSE" | grep -q '"status":"healthy"'; then
    test_pass "Health endpoint returns healthy"
else
    test_fail "Health endpoint failed: $RESPONSE"
fi

# --- Test 2: Config ---
echo -e "\n${YELLOW}Test 2: Config Endpoint${NC}"
RESPONSE=$(curl -s "$BASE_URL/api/config")
if echo "$RESPONSE" | grep -q '"defaultEngine":"gemini"'; then
    test_pass "Config returns default engine"
else
    test_fail "Config endpoint failed"
fi
if echo "$RESPONSE" | grep -q '"availableEngines"'; then
    test_pass "Config returns available engines"
else
    test_fail "Config missing availableEngines"
fi

# --- Test 3: List Documents (empty) ---
echo -e "\n${YELLOW}Test 3: List Documents${NC}"
RESPONSE=$(curl -s "$BASE_URL/api/documents/")
if echo "$RESPONSE" | grep -q '"total":'; then
    test_pass "Documents list returns total count"
else
    test_fail "Documents list failed"
fi

# --- Test 4: Upload Document ---
echo -e "\n${YELLOW}Test 4: Upload Document${NC}"
RESPONSE=$(curl -s -X POST "$BASE_URL/api/documents/upload" -F "file=@/tmp/test_document.png")
if echo "$RESPONSE" | grep -q '"document_id"'; then
    DOCUMENT_ID=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['document_id'])")
    test_pass "Document uploaded successfully (ID: $DOCUMENT_ID)"
else
    test_fail "Document upload failed: $RESPONSE"
fi
if echo "$RESPONSE" | grep -q '"status":"uploaded"'; then
    test_pass "Document status is 'uploaded'"
else
    test_fail "Document status incorrect"
fi

# --- Test 5: Get Document ---
echo -e "\n${YELLOW}Test 5: Get Document Details${NC}"
RESPONSE=$(curl -s "$BASE_URL/api/documents/$DOCUMENT_ID")
if echo "$RESPONSE" | grep -q '"id":"'$DOCUMENT_ID'"'; then
    test_pass "Document details returned"
else
    test_fail "Get document failed"
fi
if echo "$RESPONSE" | grep -q '"page_count":1'; then
    test_pass "Page count is correct"
else
    test_fail "Page count incorrect"
fi

# --- Test 6: Get Page Image ---
echo -e "\n${YELLOW}Test 6: Get Page Image${NC}"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/documents/$DOCUMENT_ID/pages/0/image")
if [ "$HTTP_CODE" = "200" ]; then
    test_pass "Page image returned (HTTP 200)"
else
    test_fail "Page image failed (HTTP $HTTP_CODE)"
fi

# --- Test 7: OCR Detection ---
echo -e "\n${YELLOW}Test 7: OCR Detection${NC}"
RESPONSE=$(curl -s -X POST "$BASE_URL/api/documents/$DOCUMENT_ID/detect")
if echo "$RESPONSE" | grep -q '"status":"ready"'; then
    test_pass "Detection completed, status is 'ready'"
else
    test_fail "Detection failed: $RESPONSE"
fi
if echo "$RESPONSE" | grep -q '"regions_detected"'; then
    REGIONS_COUNT=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['regions_detected'])")
    test_pass "Detected $REGIONS_COUNT regions"
else
    test_fail "No regions detected count in response"
fi

# --- Test 8: List Regions ---
echo -e "\n${YELLOW}Test 8: List Regions${NC}"
RESPONSE=$(curl -s "$BASE_URL/api/regions/document/$DOCUMENT_ID")
if echo "$RESPONSE" | grep -q '"total":'; then
    test_pass "Regions list returned"
else
    test_fail "Regions list failed"
fi
if echo "$RESPONSE" | grep -q '"region_type":"text"'; then
    test_pass "Text regions exist"
else
    test_fail "No text regions found"
fi
REGION_IDS=$(echo "$RESPONSE" | python3 -c "import sys,json; data=json.load(sys.stdin); print(' '.join([r['id'] for r in data['regions']]))")

# --- Test 9: Create Exclusion Zone ---
echo -e "\n${YELLOW}Test 9: Create Exclusion Zone${NC}"
RESPONSE=$(curl -s -X POST "$BASE_URL/api/regions/document/$DOCUMENT_ID/exclusion" \
    -H "Content-Type: application/json" \
    -d '{"page_number":0,"x":10,"y":10,"width":50,"height":50,"label":"Test exclusion"}')
if echo "$RESPONSE" | grep -q '"region_type":"exclusion"'; then
    EXCLUSION_ID=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
    test_pass "Exclusion zone created (ID: $EXCLUSION_ID)"
else
    test_fail "Exclusion zone creation failed: $RESPONSE"
fi

# --- Test 10: List Regions with Exclusion ---
echo -e "\n${YELLOW}Test 10: Verify Exclusion Zone${NC}"
RESPONSE=$(curl -s "$BASE_URL/api/regions/document/$DOCUMENT_ID")
if echo "$RESPONSE" | grep -q '"region_type":"exclusion"'; then
    test_pass "Exclusion zone exists in regions list"
else
    test_fail "Exclusion zone not found"
fi

# --- Test 11: Delete Exclusion Zone ---
echo -e "\n${YELLOW}Test 11: Delete Exclusion Zone${NC}"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE "$BASE_URL/api/regions/$EXCLUSION_ID")
if [ "$HTTP_CODE" = "200" ]; then
    test_pass "Exclusion zone deleted"
else
    test_fail "Delete failed (HTTP $HTTP_CODE)"
fi

# --- Test 12: Create Translation Job ---
echo -e "\n${YELLOW}Test 12: Create Translation Job${NC}"
RESPONSE=$(curl -s -X POST "$BASE_URL/api/jobs/" \
    -H "Content-Type: application/json" \
    -d "{\"document_id\":\"$DOCUMENT_ID\",\"source_language\":\"en\",\"target_language\":\"zh-Hans\",\"engine\":\"gemini\"}")
if echo "$RESPONSE" | grep -q '"id"'; then
    JOB_ID=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
    test_pass "Translation job created (ID: $JOB_ID)"
else
    test_fail "Job creation failed: $RESPONSE"
fi
if echo "$RESPONSE" | grep -q '"status":"pending"' || echo "$RESPONSE" | grep -q '"status":"running"'; then
    test_pass "Job status is pending/running"
else
    test_fail "Job status incorrect"
fi

# --- Test 13: Poll Job Status ---
echo -e "\n${YELLOW}Test 13: Poll Job Status${NC}"
sleep 2
RESPONSE=$(curl -s "$BASE_URL/api/jobs/$JOB_ID")
if echo "$RESPONSE" | grep -q '"progress"'; then
    PROGRESS=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['progress'])")
    test_pass "Job progress: $PROGRESS"
else
    test_fail "Job status poll failed"
fi

# Wait for completion
echo "   Waiting for translation to complete..."
for i in {1..30}; do
    sleep 2
    RESPONSE=$(curl -s "$BASE_URL/api/jobs/$JOB_ID")
    STATUS=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])" 2>/dev/null)
    if [ "$STATUS" = "completed" ]; then
        test_pass "Job completed!"
        break
    elif [ "$STATUS" = "failed" ]; then
        ERROR=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('error_message','unknown'))" 2>/dev/null)
        test_fail "Job failed: $ERROR"
        break
    fi
    echo "   Status: $STATUS (attempt $i/30)"
done

# --- Test 14: List Jobs ---
echo -e "\n${YELLOW}Test 14: List Jobs${NC}"
RESPONSE=$(curl -s "$BASE_URL/api/jobs/")
if echo "$RESPONSE" | grep -q '"total":'; then
    test_pass "Jobs list returned"
else
    test_fail "Jobs list failed"
fi

# --- Test 15: List Jobs for Document ---
echo -e "\n${YELLOW}Test 15: List Jobs for Document${NC}"
RESPONSE=$(curl -s "$BASE_URL/api/jobs/document/$DOCUMENT_ID")
if echo "$RESPONSE" | grep -q '"document_id":"'$DOCUMENT_ID'"'; then
    test_pass "Document jobs returned"
else
    test_fail "Document jobs failed"
fi

# --- Test 16: Download Translated File ---
echo -e "\n${YELLOW}Test 16: Download Translated File${NC}"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/documents/$DOCUMENT_ID/download/$JOB_ID")
if [ "$HTTP_CODE" = "200" ]; then
    test_pass "Download endpoint returns file (HTTP 200)"
else
    test_fail "Download failed (HTTP $HTTP_CODE)"
fi

# --- Test 17: Get Translated Page Image ---
echo -e "\n${YELLOW}Test 17: Get Translated Page Image${NC}"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/documents/$DOCUMENT_ID/pages/0/translated?job_id=$JOB_ID")
if [ "$HTTP_CODE" = "200" ]; then
    test_pass "Translated page image returned (HTTP 200)"
else
    test_fail "Translated page image failed (HTTP $HTTP_CODE)"
fi

# --- Test 18: Delete Document ---
echo -e "\n${YELLOW}Test 18: Delete Document${NC}"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE "$BASE_URL/api/documents/$DOCUMENT_ID")
if [ "$HTTP_CODE" = "200" ]; then
    test_pass "Document deleted"
else
    test_fail "Delete failed (HTTP $HTTP_CODE)"
fi

# Verify deletion
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/documents/$DOCUMENT_ID")
if [ "$HTTP_CODE" = "404" ]; then
    test_pass "Deleted document returns 404"
else
    test_fail "Deleted document still accessible (HTTP $HTTP_CODE)"
fi

# --- Summary ---
echo ""
echo "========================================"
echo "  Test Summary"
echo "========================================"
echo -e "  ${GREEN}Passed: $PASS${NC}"
echo -e "  ${RED}Failed: $FAIL${NC}"
echo "  Total:  $((PASS + FAIL))"
echo "========================================"

if [ $FAIL -eq 0 ]; then
    echo -e "\n${GREEN}🎉 All tests passed!${NC}"
    exit 0
else
    echo -e "\n${RED}⚠️  Some tests failed.${NC}"
    exit 1
fi
