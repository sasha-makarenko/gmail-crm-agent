# Gmail CRM Agent - Quick Start Guide

## Prerequisites
- Python 3.8+
- Google Cloud account with Gmail API + Sheets API enabled
- OpenAI or Anthropic API key

## Setup in 5 Minutes

### Step 1: Install Dependencies
```bash
cd gmail-crm-agent
pip install -r requirements.txt
```

### Step 2: Configure Environment
```bash
# Copy template
cp .env.example .env

# Edit .env with your details:
# - MODEL_PROVIDER (openai or anthropic)
# - API key (OPENAI_API_KEY or ANTHROPIC_API_KEY)
# - GMAIL_USER
# - GMAIL_QUERY
# - GOOGLE_SHEETS_ID
# - GOOGLE_SHEETS_TAB
```

### Step 3: Google OAuth Setup
1. Download `credentials.json` from Google Cloud Console
2. Place in project root: `gmail-crm-agent/credentials.json`
3. First run will open browser for OAuth consent

### Step 4: Test with Dry Run
```bash
# Process 5 messages without writing to Sheets
python -m agents.main --dry-run --max 5 --debug
```

### Step 5: Run for Real
```bash
# Process unprocessed messages
python -m agents.main
```

## Common Commands

```bash
# Dry run (test without writing)
python -m agents.main --dry-run

# Process last 7 days only
python -m agents.main --days 7

# Limit to 10 messages
python -m agents.main --max 10

# Debug mode (verbose)
python -m agents.main --debug

# Check statistics
python -m agents.main --status

# Clear state (reprocess all)
python -m agents.main --clear-state
```

## Expected Output

### Success
```
Gmail CRM Agent
======================================================================
Initializing components...
✓ Using LLM provider: openai
✓ Spam rules loaded from: spam_rules.yaml
✓ State store: data/processed.jsonl
✓ Google Sheets access validated
✓ Gmail labels ready

Searching Gmail with query: to:hello@example.com -in:chats
Max results: 50

Found 12 threads, 5 unprocessed

Processing threads... ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100%

Processing Complete!
┏━━━━━━━━━━━━━━━━━━━┳━━━━━━━┓
┃ Metric            ┃ Count ┃
┡━━━━━━━━━━━━━━━━━━━╇━━━━━━━┩
│ Total Processed   │ 5     │
│ Leads Found       │ 2     │
│ Spam (Denylist)   │ 1     │
│ Skipped (LLM)     │ 2     │
│ Errors            │ 0     │
└───────────────────┴───────┘
```

## Troubleshooting

### "Missing required environment variables"
Check your `.env` file has all required fields. Compare with `.env.example`.

### "Cannot access Google Sheets"
1. Verify `credentials.json` exists in project root
2. Delete `token.json` and re-authenticate
3. Check Google Sheets API is enabled in Google Cloud Console
4. Verify `GOOGLE_SHEETS_ID` in `.env` is correct

### "Spam rules not loading"
Ensure `spam_rules.yaml` exists and has valid YAML syntax.

### Too many spam detections
1. Check `spam_rules.yaml` denylist patterns
2. Add legitimate senders to allowlist in `spam_rules.yaml`

### Not enough leads found
1. LLM now defaults to "lead" when uncertain (conservative)
2. Run with `--debug` to see classification reasons
3. Check denylist isn't filtering too aggressively

## Google Sheets Setup

The agent will create this header automatically:

| Company | Address | Website | LPR Name | LPR Phone | LPR Email | Notes | Source | ThreadId | FirstSeen | LastUpdated | Status |
|---------|---------|---------|----------|-----------|-----------|-------|--------|----------|-----------|-------------|--------|

- **LPR** = Lead Point of Responsibility (primary contact)
- **Upsert by LPR Email** (lowercased, deduped)
- **Notes** merge intelligently without duplication

## File Locations

```
gmail-crm-agent/
├── .env                    # Your config (create from .env.example)
├── credentials.json        # Google OAuth (download from Cloud Console)
├── token.json             # Auto-generated on first run
├── spam_rules.yaml        # Edit to customize denylist
├── gmail_crm_agent.log    # Auto-generated logs
└── data/
    └── processed.jsonl    # Auto-generated tracking file
```

## Next Steps

1. **Customize spam rules**: Edit `spam_rules.yaml`
2. **Schedule regular runs**: Add to cron or systemd timer
3. **Monitor logs**: Check `gmail_crm_agent.log` for issues
4. **Review stats**: Run `python -m agents.main --status` regularly

## Support

Read the full documentation in `IMPLEMENTATION_SUMMARY.md` for:
- Detailed architecture
- All features and capabilities
- Advanced configuration
- Security best practices

**Ready to run!** 🚀
