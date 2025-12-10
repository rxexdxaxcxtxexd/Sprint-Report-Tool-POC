# Sprint Report Service

Automated sprint report generation service that integrates with JIRA, Fathom Video, and Claude AI to create comprehensive customer status reports.

## Overview

The Sprint Report Service automates the creation of professional sprint status reports by:
- Extracting sprint data from JIRA
- Fetching meeting recordings from Fathom Video
- Processing data through Claude AI
- Generating formatted reports (DOCX, PDF)
- Facilitating email delivery

## Prerequisites

- Python 3.9 or higher
- Docker (for N8N workflow orchestration)
- API credentials for:
  - Anthropic Claude API
  - JIRA
  - Fathom Video
- A Windows system (for document generation)

## Quick Start

### 1. Clone and Setup

```bash
cd C:\Users\layden\Projects\sprint-report-service
python -m venv venv
venv\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
# Copy the template
copy .env.template .env

# Edit .env with your credentials
# Required:
# - ANTHROPIC_API_KEY
# - FATHOM_API_KEY
# - JIRA credentials (EMAIL, TOKEN, BASE_URL)
```

### 4. Install WeasyPrint Dependencies (Windows)

For PDF generation on Windows, install GTK3 runtime:
1. Download: https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases
2. Run installer with default options
3. Verify: `python -c "import weasyprint; print('OK')"`

Alternative: Use older WeasyPrint version:
```bash
pip install weasyprint==58.1
```

### 5. Start the Service

```bash
# Start FastAPI backend
python app.py

# Or with uvicorn directly
uvicorn app:app --host 0.0.0.0 --port 8001 --reload
```

The API will be available at `http://localhost:8001`

### 6. Start N8N (Optional - for workflow automation)

```bash
# Using Docker
docker run -d \
  --name n8n-sprint-reports \
  -p 5678:5678 \
  -v C:\Users\layden\n8n-data:/home/node/.n8n \
  n8nio/n8n:latest
```

Access N8N at `http://localhost:5678`

## Project Structure

```
sprint-report-service/
├── api/              # FastAPI endpoints
├── services/         # Core business logic
├── utils/            # Helper utilities
├── templates/        # Jinja2 report templates
├── output/           # Generated reports (git-ignored)
├── tests/            # Unit and integration tests
├── config.yaml       # Service configuration
├── .env.template     # Environment variable template
└── requirements.txt  # Python dependencies
```

## Configuration

### Environment Variables (.env)

See `.env.template` for all available options. Key variables:

- `ANTHROPIC_API_KEY` - Your Claude API key
- `FATHOM_API_KEY` - Fathom Video API key
- `JIRA_*` - JIRA connection details
- `SERVICE_PORT` - Port for the FastAPI service

### config.yaml

Contains:
- JIRA board configuration
- Fathom API settings
- Report output settings
- Email configuration

## Development

### Running Tests

```bash
pytest tests/
```

### Code Style

Follow PEP 8 guidelines. Format code with:

```bash
black .
flake8 .
```

## Usage

### PDF Generation Service

Generate professional PDF reports from Markdown content:

```python
from services.pdf_generator import generate_pdf_from_markdown

# Generate PDF with template
result = generate_pdf_from_markdown(
    markdown_content="# My Report\n\nContent here...",
    output_path="C:/path/to/output.pdf",
    metadata={
        'sprint_id': 'SPRINT-123',
        'sprint_name': 'Q4 Sprint 1',
        'start_date': '2025-10-01',
        'end_date': '2025-10-14',
        'team_name': 'Engineering Team'
    },
    save_html=True
)

print(f"PDF: {result['pdf_path']}")
print(f"HTML: {result['html_path']}")
```

### Report Generation Orchestrator

Generate complete sprint reports from JIRA data:

```python
from services.report_generator import JiraClient, FathomClient, ReportGenerator
import os

# Initialize clients
jira = JiraClient(
    base_url=os.getenv('JIRA_BASE_URL'),
    email=os.getenv('JIRA_EMAIL'),
    api_token=os.getenv('JIRA_API_TOKEN')
)

fathom = FathomClient(api_key=os.getenv('FATHOM_API_KEY'))

# Create generator
generator = ReportGenerator(
    jira_client=jira,
    fathom_client=fathom,
    claude_api_key=os.getenv('ANTHROPIC_API_KEY')
)

# Generate report
result = generator.generate_report(
    sprint_id=123,
    board_id=38
)

print(f"Report: {result['metadata']['sprint_name']}")
print(f"PDF: {result['pdf_path']}")
```

### Command Line Usage

Generate a sprint report directly:

```bash
# Activate virtual environment
venv\Scripts\activate

# Generate report
python -m services.report_generator 123 38

# Test PDF generation
python -m services.pdf_generator
```

### Approval Form

Open the generated HTML approval form in a browser to review and approve/reject reports:

```bash
# After generating a report, open the approval form
start output/html/approval_form.html
```

The approval form sends decisions to your configured N8N webhook.

## Templates

### Report Template (`templates/report_template.html`)

Professional PDF output template with:
- Letter-size page layout (8.5" x 11")
- 1-inch margins
- Professional headers/footers
- Page numbering
- Company branding
- Color-coded sections
- Tables with alternating rows
- Print-optimized styling

### Approval Form (`templates/approval_form.html`)

Interactive browser-based approval interface with:
- Modern, responsive design
- Scrollable report preview
- Large action buttons (Approve/Reject)
- Webhook integration for N8N
- Confirmation dialogs
- Keyboard shortcuts (Ctrl+Enter to approve, Esc to reject)

## API Endpoints

The FastAPI service provides the following REST API endpoints:

### Core Endpoints

**POST `/api/sprint-report/generate`**
- Generate a new sprint report
- Body: `{"sprint_id": "123", "board_id": 38}`
- Returns: `{"job_id": "uuid", "status": "processing", "preview_url": "..."}`

**GET `/api/sprint-report/{job_id}/status`**
- Check report generation status
- Returns: `{"status": "processing|completed|failed", "progress": 0-100, "error": null}`

**GET `/api/sprint-report/{job_id}/preview`**
- Preview generated report (HTML)
- Returns: `{"report_html": "...", "pdf_url": "...", "metadata": {...}}`

**GET `/api/sprint-report/{job_id}/approve-form?webhook_url=...`**
- Display interactive approval form
- Query param: `webhook_url` (N8N webhook for response)
- Returns: HTML page with approve/reject buttons

**POST `/api/sprint-report/{job_id}/approve`**
- Submit approval decision
- Body: `{"approved": true, "rejection_reason": ""}`
- Returns: `{"status": "approved|rejected"}`

**GET `/api/sprint-report/{job_id}/download`**
- Download PDF report
- Returns: Binary PDF file

### Utility Endpoints

**GET `/health`**
- Health check
- Returns: `{"status": "healthy", "version": "1.0.0"}`

**GET `/`**
- Service information and API documentation links

### API Documentation

Interactive API documentation available at:
- **Swagger UI**: http://localhost:8001/docs
- **ReDoc**: http://localhost:8001/redoc

### Example Usage

```bash
# Generate report
curl -X POST http://localhost:8001/api/sprint-report/generate \
  -H "Content-Type: application/json" \
  -d '{"sprint_id": "123", "board_id": 38}'

# Check status
curl http://localhost:8001/api/sprint-report/{job_id}/status

# Download PDF
curl -O http://localhost:8001/api/sprint-report/{job_id}/download
```

## Troubleshooting

### Common Issues

**ImportError for dependencies:**
```bash
pip install --upgrade pip
pip install -r requirements.txt --force-reinstall
```

**JIRA connection issues:**
- Verify credentials in .env
- Check JIRA_BASE_URL is correct
- Ensure API token has appropriate permissions

**Fathom API issues:**
- Validate FATHOM_API_KEY
- Check rate limits on API account

**WeasyPrint PDF generation issues (Windows):**
- WeasyPrint requires GTK3 runtime libraries
- Install from: https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer
- Alternative: Use older version with fewer dependencies:
  ```bash
  pip install weasyprint==58.1
  ```
- If issues persist, the service will provide detailed error messages with installation instructions

## Contributing

1. Create a feature branch
2. Make changes with clear commits
3. Run tests and linting
4. Submit pull request

## License

Internal use only - Cornerstone Solutions Group

## Support

Contact: [team email]
