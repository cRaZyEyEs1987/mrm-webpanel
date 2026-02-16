#!/bin/bash

# MRM Webpanel - Automated Runtime Verification Script
# Tests all runtime deployments (node, python, php, wordpress)

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
API_URL="http://localhost:5000"
USERNAME="root"
PASSWORD="admin123"
TOKEN=""
RESULTS=()
FAILED_COUNT=0
SUCCESS_COUNT=0

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  STEP 1: Migrating existing deployments to fix 502 errors"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "This will update existing Node.js, Python, and PHP deployments"
echo "to use the latest fixed boilerplate code..."
echo ""

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

# Authenticate and get JWT token
authenticate() {
    log_info "Authenticating as $USERNAME..."
    
    RESPONSE=$(curl -s -X POST "$API_URL/auth/login" \
        -H "Content-Type: application/json" \
        -d "{\"username\":\"$USERNAME\",\"password\":\"$PASSWORD\"}")
    
    TOKEN=$(echo "$RESPONSE" | grep -o '"token":"[^"]*' | cut -d'"' -f4)
    
    if [ -z "$TOKEN" ]; then
        log_error "Authentication failed: $RESPONSE"
        exit 1
    fi
    
    log_success "Authenticated successfully"
}

# API call helper
api_call() {
    local METHOD="$1"
    local ENDPOINT="$2"
    local DATA="$3"
    
    if [ -z "$DATA" ]; then
        curl -s -X "$METHOD" "$API_URL$ENDPOINT" \
            -H "Authorization: Bearer $TOKEN" \
            -H "Content-Type: application/json"
    else
        curl -s -X "$METHOD" "$API_URL$ENDPOINT" \
            -H "Authorization: Bearer $TOKEN" \
            -H "Content-Type: application/json" \
            -d "$DATA"
    fi
}

# Test a runtime deployment
test_deployment() {
    local RUNTIME="$1"
    local BOILERPLATE="${2:-blank}"
    local TEST_NAME="${3:-$RUNTIME}"
    
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_info "Testing: $TEST_NAME"
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    local DOMAIN="test-${RUNTIME}-$(date +%s).local"
    local DOMAIN_ID=""
    local SITE_ID=""
    local UPSTREAM_PORT=""
    
    # Step 1: Create domain
    log_info "Creating domain: $DOMAIN with runtime: $RUNTIME"
    
    CREATE_RESPONSE=$(api_call POST "/domains" "{\"domain\":\"$DOMAIN\",\"runtime\":\"$RUNTIME\"}")
    
    DOMAIN_ID=$(echo "$CREATE_RESPONSE" | grep -o '"domain_id":[0-9]*' | cut -d':' -f2)
    
    if [ -z "$DOMAIN_ID" ]; then
        log_error "Failed to create domain: $CREATE_RESPONSE"
        RESULTS+=("$TEST_NAME: FAILED (domain creation)")
        FAILED_COUNT=$((FAILED_COUNT + 1))
        return 1
    fi
    
    log_success "Domain created with ID: $DOMAIN_ID"
    
    # Step 2: Deploy site
    log_info "Deploying site with boilerplate: $BOILERPLATE"
    
    DEPLOY_RESPONSE=$(api_call POST "/domains/$DOMAIN_ID/sites" "{\"name\":\"main\",\"boilerplate\":\"$BOILERPLATE\"}")
    
    SITE_ID=$(echo "$DEPLOY_RESPONSE" | grep -o '"site_id":[0-9]*' | cut -d':' -f2)
    
    if [ -z "$SITE_ID" ]; then
        log_error "Failed to deploy site: $DEPLOY_RESPONSE"
        RESULTS+=("$TEST_NAME: FAILED (site deployment)")
        FAILED_COUNT=$((FAILED_COUNT + 1))
        
        # Cleanup domain
        api_call DELETE "/domains/$DOMAIN_ID" > /dev/null 2>&1
        return 1
    fi
    
    log_success "Site deployed with ID: $SITE_ID"
    
    # Calculate upstream port (3000 + site_id)
    UPSTREAM_PORT=$((3000 + SITE_ID))
    
    # Step 3: Wait for container to start
    log_info "Waiting for container to start (15 seconds)..."
    sleep 15
    
    # Step 4: Check if container is running
    log_info "Checking if Docker container is running..."
    
    CONTAINER_NAME="${DOMAIN}-app"
    if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        log_success "Container $CONTAINER_NAME is running"
    else
        log_error "Container $CONTAINER_NAME is not running"
        log_info "Docker ps output:"
        docker ps --filter "name=${DOMAIN}"
        RESULTS+=("$TEST_NAME: FAILED (container not running)")
        FAILED_COUNT=$((FAILED_COUNT + 1))
        
        # Cleanup
        api_call DELETE "/domains/$DOMAIN_ID/sites/$SITE_ID" > /dev/null 2>&1
        api_call DELETE "/domains/$DOMAIN_ID" > /dev/null 2>&1
        return 1
    fi
    
    # Step 5: Test HTTP response
    log_info "Testing HTTP response on port $UPSTREAM_PORT..."
    
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$UPSTREAM_PORT" || echo "000")
    
    if [ "$HTTP_CODE" = "502" ] || [ "$HTTP_CODE" = "000" ]; then
        log_error "HTTP request failed with code: $HTTP_CODE (Gateway Error)"
        RESULTS+=("$TEST_NAME: FAILED (502 gateway error)")
        FAILED_COUNT=$((FAILED_COUNT + 1))
        
        # Show container logs
        log_info "Container logs:"
        docker logs "$CONTAINER_NAME" 2>&1 | tail -20
    elif [ "$HTTP_CODE" -ge 200 ] && [ "$HTTP_CODE" -lt 400 ]; then
        log_success "HTTP response: $HTTP_CODE (Success)"
        RESULTS+=("$TEST_NAME: PASSED")
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
    else
        log_warning "HTTP response: $HTTP_CODE (Unexpected but not gateway error)"
        RESULTS+=("$TEST_NAME: WARNING (HTTP $HTTP_CODE)")
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
    fi
    
    # Step 6: Cleanup
    log_info "Cleaning up test deployment..."
    
    api_call DELETE "/domains/$DOMAIN_ID/sites/$SITE_ID" > /dev/null 2>&1
    sleep 2
    api_call DELETE "/domains/$DOMAIN_ID" > /dev/null 2>&1
    
    # Stop and remove container if still running
    if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        docker stop "$CONTAINER_NAME" > /dev/null 2>&1 || true
        docker rm "$CONTAINER_NAME" > /dev/null 2>&1 || true
    fi
    
    log_success "Cleanup completed"
    echo ""
    sleep 3
}

# Main execution
main() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  MRM Webpanel - Automated Runtime Verification"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    # Authenticate
    authenticate
    echo ""
    
    # Migrate existing deployments first
    log_info "Migrating existing deployments to fix 502 errors..."
    MIGRATE_RESPONSE=$(api_call POST "/admin/migrate-deployments" "{}")
    
    MIGRATED=$(echo "$MIGRATE_RESPONSE" | grep -o '"migrated":[0-9]*' | cut -d':' -f2)
    FAILED=$(echo "$MIGRATE_RESPONSE" | grep -o '"failed":[0-9]*' | cut -d':' -f2)
    
    if [ -n "$MIGRATED" ]; then
        log_success "Migration complete: $MIGRATED sites updated, $FAILED failed"
    else
        log_warning "Migration response: $MIGRATE_RESPONSE"
    fi
    echo ""
    sleep 3
    
    # Test each runtime with blank boilerplate
    test_deployment "node" "blank" "Node.js 18 (blank)"
    test_deployment "python" "blank" "Python 3.11 (blank)"
    test_deployment "php" "blank" "PHP 8.2 (blank)"
    
    # Test WordPress deployment
    test_deployment "php" "wordpress" "PHP 8.2 (WordPress)"
    
    # Print summary
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  TEST RESULTS SUMMARY"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    for RESULT in "${RESULTS[@]}"; do
        if [[ "$RESULT" == *"PASSED"* ]]; then
            echo -e "${GREEN}✓${NC} $RESULT"
        elif [[ "$RESULT" == *"WARNING"* ]]; then
            echo -e "${YELLOW}!${NC} $RESULT"
        else
            echo -e "${RED}✗${NC} $RESULT"
        fi
    done
    
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "Total: ${GREEN}$SUCCESS_COUNT passed${NC}, ${RED}$FAILED_COUNT failed${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    if [ $FAILED_COUNT -gt 0 ]; then
        exit 1
    fi
    
    exit 0
}

# Run main function
main
