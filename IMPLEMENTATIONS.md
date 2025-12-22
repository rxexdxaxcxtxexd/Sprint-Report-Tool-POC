# Sprint Report Tool - Implementation Guide

This repository contains **two implementations** of the Sprint Report Tool:

## 🚀 Primary: CLI Tool (this branch)

**Location:** `main` branch
**Status:** ✅ Active Development
**Architecture:** Interactive command-line tool with JIRA MCP integration

### Key Features:
- Interactive Rich UI with step-by-step workflow
- JIRA MCP via Docker (150 lines vs 454 lines REST client)
- Persistent Docker container (60% faster)
- Timeout protection and auto-restart
- Human-in-the-loop at each decision point

### Performance:
- **~10 seconds** total startup (persistent container)
- vs **~60 seconds** per run (old Docker overhead)

### Use When:
- Running reports locally
- Need human control at each step
- Want fastest performance
- Prefer command-line workflows

### Quick Start:
```bash
cd C:\Users\layden\Projects\sprint-report-cli
python -m cli.main --sprint <SPRINT_ID>
```

---

## 📦 Archive: FastAPI Web Service

**Location:** `archive/fastapi-service` branch
**Status:** 🔒 Archived (reference only)
**Architecture:** FastAPI + N8N workflow + background jobs

### Key Features:
- REST API with 10 endpoints
- N8N workflow automation
- HTML approval form with webhooks
- Background job processing
- JIRA REST API client (custom implementation)

### Use When:
- Need web service API
- Want N8N workflow integration
- Require webhook-based approvals
- Building on existing REST patterns

### Accessing Archive:
```bash
git checkout archive/fastapi-service
# Or use the tag:
git checkout fastapi-service-v1.0
```

---

## Comparison

| Feature | CLI Tool (main) | FastAPI Service (archive) |
|---------|----------------|--------------------------|
| Interface | Interactive CLI | REST API |
| JIRA Integration | MCP (150 lines) | REST (454 lines) |
| Performance | ~10s startup | ~60s per run |
| User Control | High (each step) | Low (automated) |
| Deployment | Local execution | Web service |
| N8N Integration | N/A | ✅ Full workflow |
| Code Complexity | 2,000 lines | 7,200 lines |
| Status | Active | Archived |
| Dependencies | 11 packages | 20+ packages |

---

## Why CLI Became Primary

The CLI tool was chosen as the primary implementation due to:

1. **Simplicity** - 2,000 lines vs 7,200 lines (65% code reduction)
2. **Performance** - 6x faster startup via persistent Docker containers
3. **JIRA Integration** - MCP is 67% simpler than custom REST client
4. **Maintainability** - Fewer dependencies, clearer architecture
5. **User Control** - Human-in-the-loop provides better oversight
6. **Reliability** - Timeout protection and auto-restart prevent hangs

---

## Shared Components

Both implementations share these directories (canonical version on `main`):

- **`api/`** - External API clients (Fathom, Claude)
- **`services/`** - Report generation and PDF creation
- **`utils/`** - Configuration, validation, utilities
- **`templates/`** - HTML/PDF templates
- **`guides/`** - Sprint report guide templates

**Note:** The archive branch has frozen copies. Future updates happen on `main` only.

---

## Migration Guide

### From FastAPI to CLI

If you're migrating from the FastAPI service to the CLI tool:

1. **Configuration** - Same `.env` file works for both
2. **API Clients** - Shared `api/` directory, no changes needed
3. **Report Logic** - Shared `services/` directory, same algorithms
4. **Templates** - Same HTML/PDF templates

**Main differences:**
- Entry point: `python -m cli.main` instead of `uvicorn app:app`
- Interactive prompts instead of API endpoints
- JIRA MCP instead of REST API

### From CLI to FastAPI

If you need FastAPI features:

1. Checkout archive branch: `git checkout archive/fastapi-service`
2. Install FastAPI dependencies: `pip install -r requirements.txt`
3. Start service: `uvicorn app:app --port 8001`
4. Configure N8N workflow (see `n8n/WORKFLOW_GUIDE.md`)

---

## Documentation

### CLI Tool (main branch):
- `README.md` - Primary documentation
- `cli/main.py` - Entry point and workflow
- `cli/jira_mcp.py` - MCP integration details

### FastAPI Service (archive branch):
- `README.md` - Service documentation
- `FOR_CLAUDE.md` - Claude Code context
- `API_CLIENTS_IMPLEMENTATION.md` - API client details
- `n8n/WORKFLOW_GUIDE.md` - N8N workflow guide
- `INSTALLATION.md` - Setup instructions

---

## Branch Structure

```
main (CLI Tool - Active)
├── cli/                    # CLI interface layer
├── api/                    # Shared API clients
├── services/               # Shared business logic
├── utils/                  # Shared utilities
├── templates/              # Shared templates
└── guides/                 # Shared guides

archive/fastapi-service (FastAPI - Archived)
├── app.py                  # FastAPI application
├── n8n/                    # N8N workflow
├── api/                    # Shared (frozen copy)
├── services/               # Shared (frozen copy)
└── [documentation files]

fix/jira-mcp-integration (Feature Branch - Historical Reference)
└── Development history of MCP improvements
```

---

## Tags

For easy navigation:

- **`cli-tool-v1.0`** - CLI tool milestone (on main)
- **`fastapi-service-v1.0`** - FastAPI service archive

```bash
git checkout cli-tool-v1.0           # Latest CLI
git checkout fastapi-service-v1.0    # FastAPI archive
```

---

## Contributing

**Active development:** `main` branch (CLI tool)
**Archived (read-only):** `archive/fastapi-service` branch

All new features, bug fixes, and improvements should be made on the `main` branch.

---

## Questions?

- **"Which should I use?"** → CLI tool (main branch) for best performance
- **"Can I use FastAPI features?"** → Yes, checkout archive branch
- **"Will FastAPI be updated?"** → No, it's frozen as reference
- **"Can I migrate between them?"** → Yes, they share core components

---

**Last Updated:** December 22, 2025
**Repository:** https://github.com/rxexdxaxcxtxexd/Sprint-Report-Tool-POC
