# 🚀 GitHub Setup Instructions

Follow these steps to push your Gmail CRM Agent to GitHub.

## ✅ Pre-Push Checklist

Before running the setup script, make sure:

- [ ] You have a GitHub account
- [ ] Git is installed (`git --version`)
- [ ] You've reviewed the code for any remaining personal information
- [ ] Your `.env`, `token.json`, and `credentials.json` are gitignored

## 📋 Step-by-Step Guide

### Step 1: Run the Setup Script

```bash
cd /Users/aleksandrmakarenko/Documents/bdjola/gmail-crm-agent
./setup_github.sh
```

This script will:
- ✓ Check for sensitive files
- ✓ Backup your original README
- ✓ Initialize git repository
- ✓ Create initial commit
- ✓ Stage all files

### Step 2: Create GitHub Repository

1. Go to https://github.com/new
2. Fill in:
   - **Repository name**: `gmail-crm-agent`
   - **Description**: "🤖 AI-powered email automation that transforms Gmail inbox into structured CRM"
   - **Visibility**: Choose Public or Private
   - **IMPORTANT**: DO NOT check "Add a README", "Add .gitignore", or "Choose a license"
     (We already have these files!)
3. Click **"Create repository"**

### Step 3: Push to GitHub

GitHub will show you commands. Use these:

```bash
cd /Users/aleksandrmakarenko/Documents/bdjola/gmail-crm-agent

git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/gmail-crm-agent.git
git push -u origin main
```

**Replace `YOUR_USERNAME`** with your actual GitHub username!

### Step 4: Configure Repository Settings

On GitHub, go to your repository settings:

#### Repository Details
1. Click **"About"** (⚙️ gear icon on right side)
2. Add description:
   ```
   🤖 AI-powered email automation that transforms Gmail inbox into structured CRM. Automatically identifies leads, extracts contact info, and updates Google Sheets using GPT-4/Claude.
   ```
3. Add website (if you have one)
4. Add topics:
   ```
   ai, gmail, crm, automation, python, openai, anthropic, google-sheets,
   lead-generation, email-automation, langchain, machine-learning
   ```

#### Enable Discussions (Optional)
Settings → Features → Check "Discussions"

#### Add Social Preview Image (Optional)
Settings → General → Social Preview → Upload image

### Step 5: Update README with Your Info

Edit `README.md` and replace:
- `yourusername` → Your GitHub username (appears in 3 places)
- Contact information at the bottom

Search and replace:
```bash
# Find all instances
grep -n "yourusername" README.md

# Or use sed (be careful!)
sed -i '' 's/yourusername/YOUR_ACTUAL_USERNAME/g' README.md
```

Then commit and push:
```bash
git add README.md
git commit -m "Update README with correct GitHub username"
git push
```

### Step 6: Add Repository Secrets (for CI/CD - Optional)

If you plan to use GitHub Actions:

1. Settings → Secrets and variables → Actions
2. Add secrets:
   - `OPENAI_API_KEY`
   - `ANTHROPIC_API_KEY`
   - `GOOGLE_SHEETS_ID`

## 📝 Recommended GitHub Repository Description

**Short description** (shown in search results):
```
AI-powered email automation: Gmail → Lead Classification → CRM. Auto-extracts contacts, filters spam, updates Google Sheets.
```

**Full description** (in README):
Already in `README.md` - looks great!

**Topics** (tags for discoverability):
```
ai
gmail
crm
automation
python
openai
anthropic
google-sheets
lead-generation
email-automation
langchain
machine-learning
productivity
b2b
sales-automation
```

## 🎯 Post-Push Tasks

### Immediate
- [ ] Verify files pushed correctly
- [ ] Check README renders properly on GitHub
- [ ] Test clone on another machine
- [ ] Star your own repo 😄

### Optional Enhancements
- [ ] Add GitHub Actions for CI/CD
- [ ] Create release tags (v1.0.0)
- [ ] Add badges to README (build status, code coverage)
- [ ] Create Wiki pages
- [ ] Enable GitHub Discussions
- [ ] Add code of conduct
- [ ] Create changelog

## 🛡️ Security Double-Check

After pushing, verify these files are **NOT** on GitHub:
```bash
# On GitHub, search your repo for:
- .env
- token.json
- credentials.json
- gmail_crm_agent.log
```

If you accidentally pushed sensitive files:
```bash
# Remove from history
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch .env" \
  --prune-empty --tag-name-filter cat -- --all

git push origin --force --all
```

**Better**: Delete the repo and start fresh if you exposed secrets!

## 📢 Sharing Your Project

### README Badge Examples

Add to top of README.md:
```markdown
[![GitHub stars](https://img.shields.io/github/stars/YOUR_USERNAME/gmail-crm-agent)](https://github.com/YOUR_USERNAME/gmail-crm-agent/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/YOUR_USERNAME/gmail-crm-agent)](https://github.com/YOUR_USERNAME/gmail-crm-agent/network)
[![GitHub issues](https://img.shields.io/github/issues/YOUR_USERNAME/gmail-crm-agent)](https://github.com/YOUR_USERNAME/gmail-crm-agent/issues)
```

### Share On
- [ ] LinkedIn
- [ ] Twitter/X
- [ ] Reddit (r/Python, r/automation, r/entrepreneur)
- [ ] Hacker News
- [ ] Dev.to
- [ ] Product Hunt

Example post:
```
🤖 Just open-sourced my AI-powered Gmail CRM Agent!

Automatically transforms your Gmail inbox into a structured CRM:
✓ Filters spam using 2-stage filtering (denylist + LLM)
✓ Extracts contact info with GPT-4/Claude
✓ Updates Google Sheets automatically
✓ Multi-language support

Built for B2B companies drowning in emails.

GitHub: https://github.com/YOUR_USERNAME/gmail-crm-agent

#AI #Automation #CRM #Python #OpenAI
```

## 🎉 Success!

Your project is now on GitHub!

Next steps:
1. Monitor issues and PRs
2. Engage with community feedback
3. Keep improving based on user requests
4. Consider creating a website/landing page

## 🆘 Troubleshooting

### "Permission denied (publickey)"
```bash
# Generate SSH key
ssh-keygen -t ed25519 -C "your_email@example.com"

# Add to GitHub: Settings → SSH and GPG keys → New SSH key
cat ~/.ssh/id_ed25519.pub
```

### "Failed to push some refs"
```bash
# Pull first if remote has changes
git pull origin main --rebase
git push
```

### "Large files detected"
```bash
# Remove large files
git rm --cached large-file.txt
echo "large-file.txt" >> .gitignore
git commit --amend
```

## 📚 Resources

- [GitHub Docs](https://docs.github.com)
- [Markdown Guide](https://www.markdownguide.org/)
- [Writing Great README](https://www.makeareadme.com/)
- [Shields.io](https://shields.io/) - Badge generator

---

**Questions?** Open an issue on your new repo! 🚀
