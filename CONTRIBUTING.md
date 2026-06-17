# Contributing to Gmail CRM Agent

First off, thank you for considering contributing to Gmail CRM Agent! 🎉

## How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check existing issues. When creating a bug report, include:

- **Clear title and description**
- **Steps to reproduce** the behavior
- **Expected behavior**
- **Actual behavior**
- **Screenshots** if applicable
- **Environment details** (Python version, OS, etc.)

### Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues. When creating an enhancement suggestion, include:

- **Clear title and description**
- **Use case** - why is this enhancement useful?
- **Possible implementation** if you have ideas

### Pull Requests

1. **Fork** the repo and create your branch from `main`
2. **Make your changes**:
   - Follow the existing code style
   - Add docstrings for new functions
   - Update documentation if needed
3. **Test your changes**:
   ```bash
   python -m agents.main --dry-run --debug
   ```
4. **Commit** with a clear message:
   ```bash
   git commit -m "Add feature: XYZ"
   ```
5. **Push** to your fork and **submit a Pull Request**

## Development Setup

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/gmail-crm-agent.git
cd gmail-crm-agent

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy example configs
cp .env.example .env
cp spam_rules.example.yaml spam_rules.yaml

# Edit .env with your test credentials
```

## Code Style

- **Python**: Follow PEP 8
- **Docstrings**: Use Google-style docstrings
- **Type hints**: Add type hints for function parameters and return values
- **Comments**: Explain "why", not "what"

Example:
```python
def process_thread(
    gmail_client: GmailClient,
    thread_id: str,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Process a single Gmail thread through the full pipeline.

    Args:
        gmail_client: Gmail API client instance
        thread_id: Gmail thread ID to process
        dry_run: If True, don't write to Sheets or apply labels

    Returns:
        Dictionary with processing result including status and metadata
    """
```

## Testing

Before submitting a PR:

1. **Test with dry-run**:
   ```bash
   python -m agents.main --dry-run --max 5 --debug
   ```

2. **Check for errors**:
   ```bash
   python -m agents.main --max 1 --debug
   ```

3. **Verify documentation** is up to date

## Project Structure

```
agents/
├── config.py         # Configuration management
├── gmail_client.py   # Gmail API integration
├── sheets_client.py  # Google Sheets API
├── llm.py           # LLM provider abstraction
├── spam_filter.py   # Spam filtering logic
├── state_store.py   # Processing state tracking
└── main.py          # Main orchestration
```

## Adding New Features

### Adding a new LLM provider

1. Update `agents/llm.py`:
   - Add provider to `MODEL_PROVIDER` options
   - Implement classification/extraction methods
   - Add to `agents/config.py` validation

2. Update `.env.example`:
   - Add new API key variable
   - Document in README

### Adding new CRM fields

1. Update `agents/sheets_client.py`:
   - Add column to `HEADER_SCHEMA`
   - Update `upsert_lead()` logic

2. Update `agents/llm.py`:
   - Add field to extraction prompt
   - Update return type hints

## Questions?

Feel free to open an issue with your question, or reach out to the maintainers.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
