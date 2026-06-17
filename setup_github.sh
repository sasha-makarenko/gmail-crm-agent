#!/bin/bash
# GitHub Setup Script for Gmail CRM Agent
# This script initializes git, creates initial commit, and prepares for push

set -e  # Exit on error

echo "🚀 Gmail CRM Agent - GitHub Setup"
echo "=================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if we're in the right directory
if [ ! -f "requirements.txt" ]; then
    echo -e "${RED}❌ Error: Run this script from the gmail-crm-agent directory${NC}"
    exit 1
fi

# Step 1: Check for sensitive files
echo -e "${YELLOW}Step 1: Checking for sensitive files...${NC}"
if [ -f ".env" ] || [ -f "token.json" ] || [ -f "credentials.json" ]; then
    echo -e "${GREEN}✓ Found sensitive files (they will be gitignored)${NC}"
else
    echo -e "${YELLOW}⚠ No sensitive files found (this is OK if it's a fresh setup)${NC}"
fi
echo ""

# Step 2: Backup existing README and use GitHub version
echo -e "${YELLOW}Step 2: Preparing README...${NC}"
if [ -f "README.md" ]; then
    cp README.md README_ORIGINAL.md.bak
    echo -e "${GREEN}✓ Backed up original README to README_ORIGINAL.md.bak${NC}"
fi
cp README_GITHUB.md README.md
echo -e "${GREEN}✓ Using GitHub-optimized README${NC}"
echo ""

# Step 3: Initialize git if not already initialized
echo -e "${YELLOW}Step 3: Initializing Git repository...${NC}"
if [ ! -d ".git" ]; then
    git init
    echo -e "${GREEN}✓ Git repository initialized${NC}"
else
    echo -e "${YELLOW}⚠ Git repository already exists${NC}"
fi
echo ""

# Step 4: Create .gitkeep for empty directories
echo -e "${YELLOW}Step 4: Setting up directory structure...${NC}"
mkdir -p data state .github/ISSUE_TEMPLATE
touch data/.gitkeep state/.gitkeep
echo -e "${GREEN}✓ Created placeholder files for empty directories${NC}"
echo ""

# Step 5: Add all files
echo -e "${YELLOW}Step 5: Staging files...${NC}"
git add .
git status --short
echo -e "${GREEN}✓ Files staged for commit${NC}"
echo ""

# Step 6: Create initial commit
echo -e "${YELLOW}Step 6: Creating initial commit...${NC}"
git commit -m "Initial commit: Gmail CRM Agent

🤖 AI-powered email automation for CRM

Features:
- Two-stage spam filtering (denylist + LLM)
- Multi-provider LLM support (OpenAI/Anthropic)
- Smart contact extraction
- Google Sheets CRM integration
- Gmail labeling and organization
- Rich CLI with progress tracking
- Comprehensive documentation

🎉 Ready for production use" || echo -e "${YELLOW}⚠ No changes to commit${NC}"
echo ""

# Step 7: Instructions for GitHub
echo -e "${GREEN}✅ Setup complete!${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Create a new repository on GitHub: https://github.com/new"
echo "2. Choose repository name: gmail-crm-agent (or your preferred name)"
echo "3. Choose visibility: Public or Private"
echo "4. DO NOT initialize with README, .gitignore, or license (we already have them)"
echo ""
echo "5. Then run these commands:"
echo ""
echo -e "${GREEN}   git branch -M main${NC}"
echo -e "${GREEN}   git remote add origin https://github.com/YOUR_USERNAME/gmail-crm-agent.git${NC}"
echo -e "${GREEN}   git push -u origin main${NC}"
echo ""
echo -e "${YELLOW}Remember to replace YOUR_USERNAME with your GitHub username!${NC}"
echo ""
echo "📝 Don't forget to:"
echo "   - Update README.md contact information (search for 'yourusername')"
echo "   - Add repository description on GitHub"
echo "   - Add topics: ai, gmail, crm, automation, python, openai, anthropic"
echo ""
