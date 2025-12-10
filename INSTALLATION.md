# Installation Guide - Sprint Report Service

## Prerequisites

- Python 3.9 or higher
- pip (Python package manager)
- Virtual environment (recommended)

## Quick Installation

### 1. Navigate to Project Directory

```bash
cd C:\Users\layden\Projects\sprint-report-service
```

### 2. Create Virtual Environment (Recommended)

```bash
python -m venv venv
```

### 3. Activate Virtual Environment

**Windows (Command Prompt):**
```cmd
venv\Scripts\activate
```

**Windows (PowerShell):**
```powershell
venv\Scripts\Activate.ps1
```

**Linux/Mac:**
```bash
source venv/bin/activate
```

### 4. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

This will install all required packages:
- `anthropic>=0.34.0` - Claude API client
- `python-docx>=1.1.0` - DOCX parsing
- `pyyaml>=6.0.1` - Configuration files
- `python-dotenv>=1.0.0` - Environment variables
- `tenacity>=8.2.3` - Retry logic
- `aiohttp>=3.9.0` - Async HTTP
- Plus testing and web framework dependencies

### 5. Configure Environment Variables

```bash
# Copy template to .env
copy .env.template .env

# Edit .env with your API keys
notepad .env
```

Required environment variables:
- `ANTHROPIC_API_KEY` - Your Claude API key (get from https://console.anthropic.com/)
- `JIRA_BASE_URL` - Your JIRA instance URL
- `JIRA_EMAIL` - Your JIRA email
- `JIRA_API_TOKEN` - Your JIRA API token
- `FATHOM_API_KEY` - Your Fathom Video API key (optional)

### 6. Update Configuration

Edit `config.yaml` to set:
- JIRA board ID
- Sprint Report Guide path
- Output directory

```yaml
jira:
  default_board_id: 38  # Your board ID

sprint_report:
  guide_path: "C:\\path\\to\\your\\guide.docx"
  output_dir: "reports"
```

## Verify Installation

### Test Imports

```bash
python -c "from utils import ConfigLoader; print('Utils OK')"
python -c "from api import ClaudeReportGenerator; print('API OK')"
```

### Run Example Usage

```bash
python example_usage.py
```

This will:
1. Load and validate configuration
2. Parse Sprint Report Guide (if configured)
3. Test Claude API connection (if API key configured)
4. Generate a sample report

## Troubleshooting

### ModuleNotFoundError

```bash
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

### ANTHROPIC_API_KEY not found

Make sure you:
1. Created `.env` file from `.env.template`
2. Added your API key to `.env`
3. Restarted your terminal/IDE

### ImportError for python-docx

```bash
# Install python-docx explicitly
pip install python-docx --upgrade
```

### SSL Certificate Errors

```bash
# Update certifi
pip install --upgrade certifi
```

## Development Setup

For development with testing and type checking:

```bash
# Install all dependencies including optional ones
pip install -r requirements.txt

# Run tests
pytest tests/

# Type checking
mypy api/ utils/

# Code formatting
black .
```

## Uninstall

```bash
# Deactivate virtual environment
deactivate

# Remove virtual environment (optional)
rmdir /s venv  # Windows
rm -rf venv    # Linux/Mac
```

## Next Steps

After installation:
1. Configure your Sprint Report Guide path in `config.yaml`
2. Set up JIRA and Fathom API credentials in `.env`
3. Test with `python example_usage.py`
4. Use the utilities in your own scripts

## Support

For issues:
- Check logs for detailed error messages
- Verify API keys are correct
- Ensure file paths in config.yaml exist
- Review [README.md](README.md) for usage examples
