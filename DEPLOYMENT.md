# Deployment Guide

This guide covers deploying Gmail CRM Agent for production use.

## 🖥️ Deployment Options

### Option 1: Local Machine (Cron Job)

Best for: Small teams, simple setup

```bash
# Edit crontab
crontab -e

# Run every hour
0 * * * * cd /path/to/gmail-crm-agent && .venv/bin/python -m agents.main >> /var/log/gmail-crm-agent.log 2>&1

# Run every 4 hours
0 */4 * * * cd /path/to/gmail-crm-agent && .venv/bin/python -m agents.main

# Run daily at 9 AM
0 9 * * * cd /path/to/gmail-crm-agent && .venv/bin/python -m agents.main
```

### Option 2: Linux Server (systemd)

Best for: Always-on servers, better reliability

1. **Create systemd service**:
```bash
sudo nano /etc/systemd/system/gmail-crm-agent.service
```

2. **Add configuration**:
```ini
[Unit]
Description=Gmail CRM Agent
After=network.target

[Service]
Type=oneshot
User=your-username
WorkingDirectory=/path/to/gmail-crm-agent
ExecStart=/path/to/gmail-crm-agent/.venv/bin/python -m agents.main
StandardOutput=append:/var/log/gmail-crm-agent.log
StandardError=append:/var/log/gmail-crm-agent.log

[Install]
WantedBy=multi-user.target
```

3. **Create timer**:
```bash
sudo nano /etc/systemd/system/gmail-crm-agent.timer
```

```ini
[Unit]
Description=Run Gmail CRM Agent every 4 hours
Requires=gmail-crm-agent.service

[Timer]
OnBootSec=5min
OnUnitActiveSec=4h
Unit=gmail-crm-agent.service

[Install]
WantedBy=timers.target
```

4. **Enable and start**:
```bash
sudo systemctl daemon-reload
sudo systemctl enable gmail-crm-agent.timer
sudo systemctl start gmail-crm-agent.timer

# Check status
sudo systemctl status gmail-crm-agent.timer
sudo journalctl -u gmail-crm-agent.service
```

### Option 3: Docker

Best for: Containerized environments, cloud deployment

1. **Create Dockerfile**:
```dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY agents/ ./agents/
COPY spam_rules.yaml .

# Create directories
RUN mkdir -p data state

# Run
CMD ["python", "-m", "agents.main"]
```

2. **Create docker-compose.yml**:
```yaml
version: '3.8'
services:
  gmail-crm-agent:
    build: .
    volumes:
      - ./data:/app/data
      - ./state:/app/state
      - ./credentials.json:/app/credentials.json:ro
      - ./token.json:/app/token.json
    env_file:
      - .env
    restart: unless-stopped
```

3. **Run**:
```bash
docker-compose up -d
docker-compose logs -f
```

### Option 4: Cloud Functions

Best for: Serverless, pay-per-use

**Google Cloud Functions** (Python):
```python
# main.py
from agents.main import main as run_agent

def gmail_crm_agent(request):
    """HTTP Cloud Function entry point"""
    run_agent()
    return 'OK', 200
```

**AWS Lambda**: Similar approach with Lambda handler

## 🔐 Production Security

### Environment Variables

Never hardcode credentials. Use:

**Linux/macOS**:
```bash
# /etc/environment or ~/.bashrc
export OPENAI_API_KEY="sk-..."
export GOOGLE_SHEETS_ID="..."
```

**Docker**:
```bash
# Use docker secrets or .env file
docker secret create openai_key ./openai_key.txt
```

**systemd**:
```ini
[Service]
EnvironmentFile=/etc/gmail-crm-agent/.env
```

### Credentials Management

1. **Google OAuth**:
   - Use service account for production (no browser auth)
   - Restrict OAuth scopes to minimum required
   - Rotate tokens regularly

2. **API Keys**:
   - Use separate API keys for prod/dev
   - Set usage limits on OpenAI/Anthropic dashboards
   - Monitor usage via provider dashboards

## 📊 Monitoring

### Basic Logging

```bash
# View logs
tail -f gmail_crm_agent.log

# Search for errors
grep ERROR gmail_crm_agent.log

# Count processing stats
grep "LEAD:" gmail_crm_agent.log | wc -l
```

### Advanced Monitoring

**Option 1: Log aggregation** (ELK, Splunk, Datadog)
**Option 2: Email alerts** on errors
**Option 3: Slack/Discord webhooks**

Example email alert script:
```bash
#!/bin/bash
# alert_on_error.sh

LOG_FILE="gmail_crm_agent.log"
ERROR_COUNT=$(grep -c ERROR "$LOG_FILE")

if [ "$ERROR_COUNT" -gt 0 ]; then
    echo "Found $ERROR_COUNT errors" | mail -s "Gmail CRM Agent Errors" admin@example.com
fi
```

## 🎯 Performance Optimization

### Reduce API Costs

1. **Limit batch size**:
```bash
python -m agents.main --max 50  # Process 50 at a time
```

2. **Tune spam filter**:
   - Add more patterns to `spam_rules.yaml`
   - Reduces LLM calls (saves money)

3. **Use cheaper models**:
```bash
# .env
OPENAI_MODEL=gpt-4o-mini  # Cheaper than gpt-4
```

### Speed Improvements

1. **Parallel processing** (future enhancement)
2. **Cache LLM results** (future enhancement)
3. **Optimize Gmail query** to reduce fetched threads

## 🔄 Backup & Recovery

### Backup Important Data

```bash
# Backup script
#!/bin/bash
DATE=$(date +%Y%m%d)
tar -czf backup_$DATE.tar.gz \
    data/processed.jsonl \
    spam_rules.yaml \
    .env.example

# Upload to cloud storage
# aws s3 cp backup_$DATE.tar.gz s3://my-backups/
```

### Recovery

```bash
# Restore from backup
tar -xzf backup_20250617.tar.gz

# Reprocess if needed
python -m agents.main --clear-state
python -m agents.main
```

## 📈 Scaling

### High Volume (1000+ emails/day)

1. **Rate limiting**:
   - Gmail API: 250 quota units/user/second
   - Sheets API: 100 requests/100 seconds/user

2. **Solution**: Add delays between batches
```python
# In agents/main.py
import time
time.sleep(1)  # Add after each thread
```

3. **Database**: Consider migrating from Sheets to PostgreSQL/MySQL for large datasets

## 🧪 Testing in Production

```bash
# Dry run first
python -m agents.main --dry-run --days 1

# Small batch
python -m agents.main --max 10

# Monitor closely
python -m agents.main --debug

# Full run
python -m agents.main
```

## 🆘 Troubleshooting Production Issues

### Issue: Rate limiting
**Solution**: Add delays, reduce `MAX_THREADS`

### Issue: OAuth token expired
**Solution**: Delete `token.json`, re-authenticate

### Issue: Memory issues
**Solution**: Process in smaller batches with `--max`

### Issue: Disk space
**Solution**: Rotate logs, clean old `data/processed.jsonl`

## 📞 Support

For production issues:
1. Check logs: `gmail_crm_agent.log`
2. Run with `--debug`
3. Open GitHub issue with logs

## 🚀 Next Steps

- [ ] Set up monitoring
- [ ] Configure backups
- [ ] Test failover scenarios
- [ ] Document runbooks
- [ ] Set up alerting
