#!/bin/bash
set -euo pipefail

# Install curl if not available
if command -v apk &> /dev/null; then
    apk add --no-cache curl bash nodejs npm
elif command -v apt-get &> /dev/null; then
    apt-get update && apt-get install -y curl
elif command -v yum &> /dev/null; then
    yum install -y curl
else
    echo "Warning: No known package manager found, assuming curl is available" >&2
fi

if command -v apk &> /dev/null; then
    # Alpine/musl: use npm-based Claude Code (bypasses native binary issues entirely)
    
    npm install -g @anthropic-ai/claude-code@2.1.81
    
else
    # Standard glibc install — use official installer
    
    curl -fsSL https://claude.ai/install.sh | bash -s -- 2.1.81
    
fi

echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc

export PATH="$HOME/.local/bin:$PATH"
claude --version