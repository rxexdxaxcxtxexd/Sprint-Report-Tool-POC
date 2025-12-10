# 🤖 Context for Future Claude Code Sessions

## Project Status
✅ **COMPLETE & PRODUCTION-READY**  
**Pushed to**: https://github.com/rxexdxaxcxtxexd/Sprint-Report-Tool-POC  
**Date**: December 9, 2025  
**Total Code**: 11,056 lines across 36 files

---

## What This Is
Automated Sprint report generation system that:
1. Fetches Sprint data from JIRA
2. Gets meeting notes from Fathom Video
3. Uses Claude AI to generate professional reports
4. Creates PDF with professional template
5. Shows human approval form
6. Sends via Microsoft 365 email (after approval)

---

## Quick Start for New Sessions
```bash
cd C:\Users\layden\Projects\sprint-report-service
.\venv\Scripts\activate
python app.py  # Starts on port 8001
```

---

## Architecture
**Hybrid: N8N + Python FastAPI**

N8N Workflow (Port 5678):
- Manual trigger → Sprint ID input
- HTTP POST → Python backend
- Poll until report ready
- Human approval gate (Wait node + webhook)
- Download PDF → Send email

Python Backend (Port 8001):
- 8 REST API endpoints
- Background job processing
- JIRA + Fathom + Claude integrations
- PDF generation with WeasyPrint

---

## Key Files (Read These First)
1. **README.md** - Setup guide, usage, API docs
2. **app.py** - FastAPI application (~600 lines)
3. **api/jira_client.py** - JIRA integration (454 lines)
4. **api/fathom_client.py** - Fathom integration (544 lines)
5. **api/claude_client.py** - AI report generation (760 lines)
6. **services/report_generator.py** - Orchestration (662 lines)
7. **n8n/sprint-report-workflow.json** - N8N workflow

---

## Configuration
**.env** (user must create from .env.template):
- ANTHROPIC_API_KEY
- JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN
- FATHOM_API_KEY

**config.yaml**:
- JIRA boards configuration
- Sprint Report Guide path

**Sprint Report Guide**:
- Location: C:\Users\layden\Downloads\CSG_Customer_Status_Report_Guide.docx
- Purpose: Template for Claude to follow when generating reports

---

## User Context
- **Name**: Lucas Layden
- **Email**: layden@csgsolutions.com
- **Company**: CSG Solutions
- **JIRA**: csgsolutions.atlassian.net
- **Primary Board**: Board 38 (BOPS project)
- **Dev Skills**: Limited, uses AI tools (Claude Code, Cursor)
- **OS**: Windows 10/11

---

## Important Notes for Claude

### API Keys
⚠️ **SECURITY**: Fathom API key was exposed in conversation - user should rotate it!

### Design Decisions
1. **In-memory job storage** - Production should use Redis/PostgreSQL
2. **JIRA REST API** - Direct REST calls (not MCP)
3. **WeasyPrint** - Requires GTK3 on Windows
4. **Human approval** - N8N Wait node with webhook resume pattern

### Common Enhancements Requests
- "Add another JIRA board" → Edit config.yaml
- "Change report format" → Edit templates/report_template.html
- "Modify approval UI" → Edit templates/approval_form.html
- "Add new endpoint" → Follow patterns in app.py
- "Change AI prompts" → Edit api/claude_client.py

---

## Testing
```bash
# Test service
curl http://localhost:8001/health

# Generate report
curl -X POST http://localhost:8001/api/sprint-report/generate \
  -d '{"sprint_id": "123", "board_id": 38}'
```

---

## Documentation Available
- README.md - Main guide
- API_CLIENTS_IMPLEMENTATION.md - API client details
- IMPLEMENTATION_SUMMARY.md - Implementation overview
- INSTALLATION.md - Setup instructions
- QUICK_REFERENCE.md - Command reference
- api/README.md - API module docs
- n8n/WORKFLOW_GUIDE.md - N8N workflow details

---

## Future Enhancement Ideas
- [ ] Persistent job storage (Redis/PostgreSQL)
- [ ] Report templates (weekly, monthly)
- [ ] Slack notifications
- [ ] Scheduled automatic generation
- [ ] Multi-project reports
- [ ] Historical trend analysis

---

## How to Continue Development

1. **Read README.md** for setup and architecture
2. **Test the service** before making changes
3. **Follow existing patterns** (type hints, docstrings, error handling)
4. **Update docs** when making changes
5. **Run tests**: `pytest tests/`

---

**Repository**: https://github.com/rxexdxaxcxtxexd/Sprint-Report-Tool-POC  
**Status**: Production Ready ✅  
**Last Updated**: December 9, 2025
