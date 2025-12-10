# Quick Reference - Sprint Report Service Utilities

## File Locations

```
C:\Users\layden\Projects\sprint-report-service\
├── api\claude_client.py       # Claude API integration (760 lines)
├── utils\config_loader.py     # Configuration management (468 lines)
└── utils\docx_parser.py       # DOCX parsing (610 lines)
```

---

## 1. Configuration Loader (`utils/config_loader.py`)

### Import
```python
from utils import ConfigLoader
```

### Basic Usage
```python
# Initialize
config = ConfigLoader("config.yaml")

# Get values with dot notation
board_id = config.get("jira.default_board_id")
model = config.get("claude.model", default="claude-opus-4-5-20251101")

# Get environment variables
api_key = config.get_env_var("ANTHROPIC_API_KEY", required=True)
port = config.get_env_var("SERVICE_PORT", default="8001")

# Get board configuration
board_config = config.get_board_config(38)
print(board_config["name"])  # "BOPS Board"

# Validate configuration
validation = config.validate()
if validation["errors"]:
    print(f"Errors: {validation['errors']}")
```

### Available Functions
| Function | Purpose |
|----------|---------|
| `ConfigLoader(path)` | Main class for config management |
| `load_config(path)` | Load YAML file |
| `get_board_config(board_id)` | Get board-specific config |
| `get_env_var(key, default, required)` | Get environment variable |
| `get_claude_config()` | Get Claude API config |
| `get_sprint_guide_path()` | Get Sprint guide path |

---

## 2. DOCX Parser (`utils/docx_parser.py`)

### Import
```python
from utils import parse_sprint_guide, extract_sections, validate_guide
```

### Basic Usage
```python
# Parse entire document
guide_text = parse_sprint_guide("guide.docx")
print(guide_text[:500])  # First 500 chars

# Extract sections
sections = extract_sections("guide.docx")
for section_name, content in sections.items():
    print(f"\n# {section_name}\n{content}")

# Validate guide structure
validation = validate_guide("guide.docx")
print(f"Valid: {validation['valid']}")
print(f"Sections found: {validation['sections_found']}")
print(f"Missing: {validation['missing_sections']}")

# Get specific section
overview = get_section("guide.docx", "Sprint Overview")
if overview:
    print(overview)

# Get document statistics
stats = get_document_stats("guide.docx")
print(f"Words: {stats['word_count']}")
print(f"Paragraphs: {stats['paragraph_count']}")
```

### Available Functions
| Function | Purpose |
|----------|---------|
| `parse_sprint_guide(path)` | Extract all text |
| `extract_sections(path)` | Get sections by headings |
| `validate_guide(path)` | Validate guide structure |
| `get_section(path, name)` | Get specific section |
| `get_document_stats(path)` | Get document statistics |

### Expected Sections
- Sprint Overview
- Completed Work
- In Progress
- Blockers and Risks
- Metrics
- Next Sprint Plan

---

## 3. Claude API Client (`api/claude_client.py`)

### Import
```python
from api import ClaudeReportGenerator
```

### Basic Usage
```python
# Initialize generator
generator = ClaudeReportGenerator(
    model="claude-opus-4-5-20251101",
    max_tokens=8192,
    temperature=0.7
)

# Generate report (async)
report = await generator.generate_sprint_report(
    sprint_guide=guide_content,
    jira_data={
        "completed": [...],
        "in_progress": [...],
        "metrics": {...}
    },
    meeting_notes=[
        {"date": "2025-12-01", "title": "Standup", "summary": "..."}
    ],
    sprint_metadata={
        "sprint_id": "SPRINT-45",
        "sprint_name": "Sprint 45",
        "start_date": "2025-11-25",
        "end_date": "2025-12-08",
        "goal": "Complete authentication"
    }
)

# Validate report
validation = generator.validate_report(report)
if validation["valid"]:
    print(f"Report OK: {validation['word_count']} words")
else:
    print(f"Missing: {validation['missing_sections']}")

# Save report
with open("reports/sprint-45.md", "w") as f:
    f.write(report)
```

### One-Line Usage
```python
from api.claude_client import generate_report

report = await generate_report(
    sprint_guide_path="guide.docx",
    jira_data=jira_data,
    meeting_notes=notes,
    sprint_metadata=metadata
)
```

### Batch Processing
```python
# Generate multiple reports concurrently
configs = [
    {
        "sprint_guide": guide,
        "jira_data": data1,
        "meeting_notes": notes1,
        "sprint_metadata": meta1
    },
    # ... more configs
]

results = await generator.generate_multiple_reports(
    configs,
    max_concurrent=3  # Max 3 API calls at once
)

for result in results:
    if result["success"]:
        print(f"✓ {result['sprint_id']}")
    else:
        print(f"✗ {result['sprint_id']}: {result['error']}")
```

### Available Methods
| Method | Purpose |
|--------|---------|
| `generate_sprint_report()` | Generate report (async) |
| `validate_report()` | Validate generated report |
| `generate_multiple_reports()` | Batch generation (async) |

---

## Common Workflows

### Complete Report Generation
```python
import asyncio
from utils import ConfigLoader, parse_sprint_guide
from api import ClaudeReportGenerator

async def generate_report():
    # 1. Load config
    config = ConfigLoader("config.yaml")

    # 2. Parse guide
    guide_path = config.get("sprint_report.guide_path")
    guide = parse_sprint_guide(guide_path)

    # 3. Prepare data (fetch from JIRA/Fathom)
    jira_data = fetch_jira_sprint_data(...)
    meeting_notes = fetch_fathom_notes(...)

    # 4. Generate report
    generator = ClaudeReportGenerator()
    report = await generator.generate_sprint_report(
        sprint_guide=guide,
        jira_data=jira_data,
        meeting_notes=meeting_notes,
        sprint_metadata={...}
    )

    # 5. Save report
    output_dir = config.get("sprint_report.output_dir")
    with open(f"{output_dir}/report.md", "w") as f:
        f.write(report)

    print("Report generated successfully!")

asyncio.run(generate_report())
```

### Validate Sprint Guide
```python
from utils import validate_guide, get_document_stats

# Validate structure
validation = validate_guide("guide.docx")

print(f"Valid: {validation['valid']}")
print(f"Sections found: {len(validation['sections_found'])}")

if validation['missing_sections']:
    print("\nMissing sections:")
    for section in validation['missing_sections']:
        print(f"  - {section}")

if validation['warnings']:
    print("\nWarnings:")
    for warning in validation['warnings']:
        print(f"  - {warning}")

# Get statistics
stats = get_document_stats("guide.docx")
print(f"\nDocument has {stats['word_count']} words in {stats['paragraph_count']} paragraphs")
```

### Configuration Management
```python
from utils import ConfigLoader

config = ConfigLoader("config.yaml")

# Validate all configuration
validation = config.validate()

if validation["errors"]:
    print("Configuration errors:")
    for error in validation["errors"]:
        print(f"  ✗ {error}")
else:
    print("✓ Configuration valid")

if validation["warnings"]:
    print("\nWarnings:")
    for warning in validation["warnings"]:
        print(f"  ⚠ {warning}")

# Get board config
try:
    board = config.get_board_config()
    print(f"\nDefault board: {board['name']} (ID: {board['id']})")
except Exception as e:
    print(f"Error: {e}")
```

---

## Error Handling

### Configuration Errors
```python
from utils import ConfigLoader, ConfigurationError

try:
    config = ConfigLoader("config.yaml")
    api_key = config.get_env_var("ANTHROPIC_API_KEY", required=True)
except ConfigurationError as e:
    print(f"Configuration error: {e}")
    # Handle: prompt user, use defaults, exit
```

### DOCX Parsing Errors
```python
from utils import parse_sprint_guide, DOCXParsingError

try:
    guide = parse_sprint_guide("guide.docx")
except FileNotFoundError:
    print("Guide file not found")
except DOCXParsingError as e:
    print(f"DOCX parsing error: {e}")
```

### Claude API Errors
```python
from api import ClaudeReportGenerator, ClaudeAPIError, ReportValidationError

try:
    generator = ClaudeReportGenerator()
    report = await generator.generate_sprint_report(...)
except ClaudeAPIError as e:
    print(f"API error: {e}")
    # Retry, use cached report, notify user
except ReportValidationError as e:
    print(f"Validation error: {e}")
    # Use partial report, regenerate
```

---

## Environment Variables

Required in `.env`:
```bash
ANTHROPIC_API_KEY=sk-ant-...           # Required for Claude API
JIRA_BASE_URL=https://....atlassian.net # Required for JIRA
JIRA_EMAIL=your-email@company.com       # Required for JIRA
JIRA_API_TOKEN=your-token               # Required for JIRA
FATHOM_API_KEY=your-key                 # Optional for Fathom
```

---

## Configuration (`config.yaml`)

Required settings:
```yaml
jira:
  default_board_id: 38
  boards:
    38:
      name: "Board Name"
      project: "PROJECT"
      url: "https://..."

sprint_report:
  guide_path: "C:\\path\\to\\guide.docx"
  output_dir: "reports"

claude:
  model: "claude-opus-4-5-20251101"
  max_tokens: 8192
  temperature: 0.7
```

---

## Testing

### Run Example
```bash
python example_usage.py
```

### Run Tests
```bash
pytest tests/test_config_loader.py -v
```

### Test Imports
```bash
python -c "from utils import ConfigLoader; print('OK')"
python -c "from utils import parse_sprint_guide; print('OK')"
python -c "from api import ClaudeReportGenerator; print('OK')"
```

---

## Troubleshooting

### ModuleNotFoundError: anthropic
```bash
pip install -r requirements.txt
```

### ANTHROPIC_API_KEY not found
```bash
# Create .env file
copy .env.template .env
# Add your API key to .env
```

### Guide file not found
```yaml
# Update config.yaml
sprint_report:
  guide_path: "C:\\correct\\path\\to\\guide.docx"
```

### Import errors
```bash
# Ensure you're in project directory
cd C:\Users\layden\Projects\sprint-report-service
# Activate virtual environment
venv\Scripts\activate
```

---

## Performance Tips

1. **Use async for multiple reports**: `generate_multiple_reports()` for batch processing
2. **Configure max_concurrent**: Control API rate (default: 3 concurrent)
3. **Cache guide content**: Parse DOCX once, reuse for multiple reports
4. **Validate before API call**: Check inputs to avoid wasted API calls
5. **Monitor token usage**: Check logs for token consumption

---

## Support

- **Installation**: See `INSTALLATION.md`
- **Examples**: See `example_usage.py`
- **Details**: See `IMPLEMENTATION_SUMMARY.md`
- **Tests**: Run `pytest tests/ -v`

---

**Quick Links**:
- Configuration: `config.yaml`
- Environment: `.env.template`
- Installation: `INSTALLATION.md`
- Examples: `example_usage.py`
- Summary: `IMPLEMENTATION_SUMMARY.md`
