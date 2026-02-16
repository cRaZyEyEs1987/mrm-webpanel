#!/bin/bash
set -e

# MRM Template Builder
# Builds pre-configured Docker images with dependencies already installed

TEMPLATES_DIR="/srv/mrm/templates"
LOG_FILE="/var/log/mrm-template-builder.log"

echo "=== MRM Template Builder ===" | tee -a "$LOG_FILE"
echo "Starting at $(date)" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Function to build a template
build_template() {
    local runtime=$1
    local version=$2
    local image_tag=$3
    
    local template_path="$TEMPLATES_DIR/$runtime/$version"
    
    if [ ! -f "$template_path/.mrm-template" ]; then
        echo "⚠️  Skipping $runtime/$version - not a valid template" | tee -a "$LOG_FILE"
        return 1
    fi
    
    echo "🔨 Building $runtime/$version → $image_tag" | tee -a "$LOG_FILE"
    
    if docker build -t "$image_tag" "$template_path" >> "$LOG_FILE" 2>&1; then
        echo "✅ Successfully built $image_tag" | tee -a "$LOG_FILE"
        
        # Verify the image
        if docker inspect "$image_tag" > /dev/null 2>&1; then
            echo "✓  Image verified: $image_tag" | tee -a "$LOG_FILE"
            return 0
        else
            echo "❌ Image verification failed: $image_tag" | tee -a "$LOG_FILE"
            return 1
        fi
    else
        echo "❌ Build failed for $image_tag" | tee -a "$LOG_FILE"
        return 1
    fi
}

# Build Node.js templates
echo "=== Building Node.js Templates ===" | tee -a "$LOG_FILE"
build_template "node" "node18" "mrm/node:18"
build_template "node" "node20" "mrm/node:20"
build_template "node" "node21" "mrm/node:21"

echo "" | tee -a "$LOG_FILE"

# Build Python templates
echo "=== Building Python Templates ===" | tee -a "$LOG_FILE"
build_template "python" "python310" "mrm/python:310"
build_template "python" "python311" "mrm/python:311"
build_template "python" "python312" "mrm/python:312"

echo "" | tee -a "$LOG_FILE"

# Build PHP templates
echo "=== Building PHP Templates ===" | tee -a "$LOG_FILE"
build_template "php" "php82" "mrm/php:82"
build_template "php" "php83" "mrm/php:83"

echo "" | tee -a "$LOG_FILE"
echo "=== Build Summary ===" | tee -a "$LOG_FILE"
docker images | grep "^mrm/" | tee -a "$LOG_FILE"

echo "" | tee -a "$LOG_FILE"
echo "✅ Template build completed at $(date)" | tee -a "$LOG_FILE"
echo "📋 Full log: $LOG_FILE"
