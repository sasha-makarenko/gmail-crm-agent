# Gmail CRM Agent - Implementation Summary

## Overview
The Gmail CRM Agent has been completely refactored to meet all requirements for reliable Gmail reading, classification, entity extraction, and Google Sheets integration with spam filtering.

## ✅ All Requirements Implemented

### 1. Gmail API ✓
- **Configurable search query** via `GMAIL_QUERY` env var
- **Full thread fetching** with all messages
- **HTML fallback** using `html2text` library for better text extraction
- **Idempotency**: `data/processed.jsonl` stores messageId + reason + timestamp

### 2. Spam Rules ✓
- **Denylist file**: `spam_rules.yaml` with structure:
  - `allowlist`: emails/domains that bypass all filters
  - `denylist_emails`: exact email matches
  - `denylist_domains`: domain substring matches
  - `denylist_regex`: pattern matching with reasons
  - `company`: outgoing company emails to skip
- **Pre-LLM filtering**: Denylist checked BEFORE any LLM calls (saves costs)

### 3. LLM Classification ✓
- **Multi-provider support**: `MODEL_PROVIDER` env switch (anthropic/openai)
- **Conservative spam detection**: Defaults to "lead" when uncertain
- **Returns**: `is_lead`, `reason`, `confidence`
- **Supported providers**:
  - OpenAI (gpt-4o-mini default)
  - Anthropic (claude-3-5-sonnet-20241022 default)

### 4. Entity Extraction ✓
- **One LLM call** producing strict JSON
- **Fields extracted**: `{company, address, website, lpr_name, lpr_phone, lpr_email}`
- **Empty strings** for unknown fields (never null)
- **Multi-language support**: Russian, English, German, etc.
- **Email fallback**: Uses From header if LLM doesn't extract

### 5. Notes ✓
- **1-2 sentence summary** in Russian
- **Thread-aware**: Merges with existing notes without duplication
- **Timestamped updates**: `[YYYY-MM-DD HH:MM:SS] New content`
- **Smart deduplication**: Doesn't repeat identical content

### 6. Google Sheets ✓
- **Header schema**:
  ```
  Company | Address | Website | LPR Name | LPR Phone | LPR Email |
  Notes | Source | ThreadId | FirstSeen | LastUpdated | Status
  ```
- **Upsert by LPR Email** (lowercased, column F)
- **Smart updates**:
  - Preserves `FirstSeen` on updates
  - Merges `Notes` intelligently
  - Only overwrites empty fields
  - Updates `LastUpdated` and `Status`

### 7. CLI Flags ✓
```bash
python -m agents.main --dry-run          # Test without writing
python -m agents.main --days 7           # Process last 7 days
python -m agents.main --max 10           # Limit to 10 messages
python -m agents.main --debug            # Verbose logging
python -m agents.main --status           # Show statistics
python -m agents.main --clear-state      # Reset processed state
```

### 8. Per-Message Logging ✓
Each message logs:
- **Sender**: email address
- **Label**: ai_lead / ai_skip / ai_error
- **Action**: inserted / updated / skipped / error
- **Reason**: Why classified as spam/lead/skip

Example log:
```
Processing thread 123abc from customer@example.com: Product inquiry...
  → SPAM (denylist): Denylist: domain match | Rule: linkedin.com

Processing thread 456def from lead@bakery.de: Wholesale order...
  → Passed denylist, classifying with LLM...
  → LEAD detected, extracting contact info...
  → LEAD: lead@bakery.de | Action: inserted
```

---

## New Files Created

### Core Modules
1. **`agents/config.py`** - Centralized configuration with env validation
2. **`agents/spam_filter.py`** - Pre-LLM spam filtering
3. **`spam_rules.yaml`** - Denylist configuration

### Modified Files
1. **`agents/main.py`** - Complete rewrite with CLI args + pipeline integration
2. **`agents/llm.py`** - Multi-provider support + conservative classification
3. **`agents/gmail_client.py`** - html2text integration
4. **`agents/sheets_client.py`** - New header schema + smart upsert
5. **`agents/state_store.py`** - JSONL format with metadata
6. **`requirements.txt`** - Added html2text, pyyaml, anthropic
7. **`.env.example`** - Updated with all new env vars

---

## Environment Variables

### Required
```bash
# LLM Provider (choose one)
MODEL_PROVIDER=openai  # or "anthropic"

# OpenAI (if MODEL_PROVIDER=openai)
OPENAI_API_KEY=your_key
OPENAI_MODEL=gpt-4o-mini  # optional

# Anthropic (if MODEL_PROVIDER=anthropic)
ANTHROPIC_API_KEY=your_key
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022  # optional

# Gmail
GMAIL_USER=your@email.com
GMAIL_QUERY=to:your@email.com -in:chats

# Google Sheets
GOOGLE_SHEETS_ID=your_sheet_id
GOOGLE_SHEETS_TAB=Leads
```

### Optional (with defaults)
```bash
GOOGLE_TOKEN_PATH=token.json
SPAM_RULES=spam_rules.yaml
PROCESSED_STORE=data/processed.jsonl
MAX_THREADS=50
```

---

## Processing Pipeline

```
1. Gmail Search
   ↓
2. Fetch Thread (full message + headers)
   ↓
3. Convert to Text (html2text fallback)
   ↓
4. ⚡ SPAM FILTER CHECK (denylist) ← BEFORE LLM
   ↓
   ├─ SPAM → Label: ai_skip, Store: spam
   └─ PASS
      ↓
5. LLM Classification
   ↓
   ├─ NOT LEAD → Label: ai_skip, Store: skip
   └─ LEAD
      ↓
6. Extract Contact Info (LLM)
   ↓
7. Generate Summary (LLM)
   ↓
8. Upsert to Sheets (by LPR Email lowercased)
   ↓
9. Apply Gmail Label: ai_lead
   ↓
10. Store to data/processed.jsonl
```

---

## File Structure

```
gmail-crm-agent/
├── .env                      # Your config (update from .env.example)
├── .env.example              # Template ✨ UPDATED
├── spam_rules.yaml           # Denylist config ✨ NEW
├── credentials.json          # Google OAuth (don't commit)
├── token.json                # OAuth token (don't commit)
├── requirements.txt          # Dependencies ✨ UPDATED
├── data/
│   └── processed.jsonl       # Message tracking ✨ NEW FORMAT
├── agents/
│   ├── config.py             # Config module ✨ NEW
│   ├── spam_filter.py        # Spam filtering ✨ NEW
│   ├── main.py               # Main entrypoint ✨ REWRITTEN
│   ├── llm.py                # Multi-provider LLM ✨ REWRITTEN
│   ├── gmail_client.py       # Gmail API ✨ ENHANCED
│   ├── sheets_client.py      # Sheets API ✨ ENHANCED
│   ├── state_store.py        # State tracking ✨ REWRITTEN
│   └── utils.py              # Utilities (unchanged)
└── state/
    └── processed_threads.json  # Old format (can delete)
```

---

## Installation & Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
# Copy and edit .env
cp .env.example .env
# Add your API keys and configuration
```

### 3. Customize Spam Rules
Edit `spam_rules.yaml` to add your denylist patterns.

### 4. Run
```bash
# Test with dry-run first
python -m agents.main --dry-run --max 5

# Process for real
python -m agents.main

# Check status
python -m agents.main --status
```

---

## Key Features

### Idempotency
- Every processed message stored in `data/processed.jsonl`
- Format: `{"message_id": "...", "timestamp": "...", "reason": "lead/spam/skip/error", "metadata": {...}}`
- Re-running won't duplicate processing

### Error Handling
- Human-readable errors (no stack traces to console)
- Errors logged to `gmail_crm_agent.log`
- Failed threads labeled with `ai_error`

### Type Safety
- Type hints throughout
- Docstrings for all functions
- Clear parameter documentation

### Robustness
- Retry logic with exponential backoff (Gmail + Sheets APIs)
- Rate limiting (100ms between requests)
- Graceful degradation (fallbacks for HTML, JSON parsing, etc.)

---

## Testing Checklist

### Phase 1: Dry Run
```bash
# Test with small batch
python -m agents.main --dry-run --max 5 --debug

# Verify:
# ✓ Spam rules load correctly
# ✓ Gmail connection works
# ✓ LLM provider connects
# ✓ No errors in classification/extraction
```

### Phase 2: Real Run (Small)
```bash
# Process 5 real messages
python -m agents.main --max 5

# Verify:
# ✓ Sheets header created with correct schema
# ✓ Leads inserted with all fields
# ✓ Gmail labels applied
# ✓ data/processed.jsonl created
```

### Phase 3: Full Run
```bash
# Process all unprocessed
python -m agents.main

# Verify:
# ✓ No duplicate processing
# ✓ Updates vs inserts work correctly
# ✓ Notes merge without duplication
```

---

## Common Issues & Solutions

### Issue: "Missing required environment variables"
**Solution**: Check `.env` file has all required vars. Compare with `.env.example`.

### Issue: "Cannot access Google Sheets"
**Solution**:
1. Ensure `credentials.json` exists
2. Delete `token.json` and re-authenticate
3. Check Google Sheets API is enabled
4. Verify spreadsheet ID is correct

### Issue: "Spam rules not loading"
**Solution**: Check `spam_rules.yaml` exists and has valid YAML syntax.

### Issue: "Too many spam detections"
**Solution**:
1. Check denylist patterns in `spam_rules.yaml`
2. Add false positives to allowlist
3. Adjust regex patterns

### Issue: "Not enough leads found"
**Solution**: LLM is now conservative (defaults to lead). Check:
1. Denylist isn't too aggressive
2. Run with `--debug` to see classification reasons

---

## Next Steps (Optional Enhancements)

1. **Gmail query by date**: Already supported via `--days N` flag
2. **Webhook/scheduling**: Add cron job or systemd timer
3. **Multi-language notes**: Currently Russian, could make configurable
4. **Custom fields**: Easy to extend `lead_data` dict in main.py
5. **Duplicate detection**: By name+domain (add to `_find_row_by_email`)

---

## Security Notes

### DO NOT COMMIT:
- `.env` (contains API keys)
- `token.json` (OAuth token)
- `credentials.json` (Google OAuth credentials)

### Safe to commit:
- `.env.example` (template only)
- `spam_rules.yaml` (contains no secrets)
- `data/processed.jsonl` (contains only IDs, safe)

---

## Summary of Changes

| Component | Status | Changes |
|-----------|--------|---------|
| Configuration | ✅ New | Centralized config with validation |
| Spam Filter | ✅ New | Pre-LLM denylist checking |
| LLM Processor | ✅ Rewritten | Multi-provider + conservative |
| Gmail Client | ✅ Enhanced | html2text fallback |
| Sheets Client | ✅ Enhanced | New schema + smart upsert |
| State Store | ✅ Rewritten | JSONL format with metadata |
| Main Pipeline | ✅ Rewritten | CLI args + full integration |
| Dependencies | ✅ Updated | Added html2text, pyyaml, anthropic |

**Total Files Created**: 3
**Total Files Modified**: 7
**Lines of Code Added**: ~2000
**All Requirements**: ✅ Implemented

---

## Contact & Support

For issues or questions:
1. Check this document first
2. Review logs in `gmail_crm_agent.log`
3. Run with `--debug` for verbose output
4. Check `data/processed.jsonl` for processing history

---

**Implementation Complete** 🎉
All required capabilities have been implemented and are ready for testing.
