"""
Sprint Report Service - FastAPI Application

Production-ready web service for automated Sprint report generation using JIRA, Fathom, and Claude AI.

This service provides REST API endpoints for:
- Generating Sprint reports with background job processing
- Checking job status and progress
- Previewing generated reports
- Approving/rejecting reports
- Downloading PDF reports

Architecture:
    - FastAPI web framework with async support
    - In-memory job storage (MVP, replace with Redis for production)
    - Background task processing for report generation
    - CORS enabled for N8N integration
    - Comprehensive error handling and logging

Example N8N workflow:
    1. Trigger: Sprint completion event
    2. HTTP POST to /api/sprint-report/generate
    3. Poll /api/sprint-report/{job_id}/status until complete
    4. Open /api/sprint-report/{job_id}/approve-form in browser
    5. Wait for webhook callback from approval form
    6. If approved, send report to stakeholders

Environment Variables Required:
    - JIRA_BASE_URL: JIRA instance URL
    - JIRA_EMAIL: JIRA user email
    - JIRA_API_TOKEN: JIRA API token
    - ANTHROPIC_API_KEY: Claude API key
    - FATHOM_API_KEY: Fathom API key (optional)
    - SERVICE_PORT: Port to run service on (default: 8001)

Author: Sprint Report Service
Version: 1.0.0
"""

import os
import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from jinja2 import Template

from services.report_generator import (
    ReportGenerator,
    JiraClient,
    FathomClient,
    ReportGenerationError,
    JiraAPIError,
    FathomAPIError,
    ClaudeAPIError
)
from utils.config_loader import ConfigLoader


# ============================================================================
# Configuration & Setup
# ============================================================================

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('sprint_report_service.log')
    ]
)
logger = logging.getLogger(__name__)


# ============================================================================
# Pydantic Models (Request/Response Schemas)
# ============================================================================

class SprintReportRequest(BaseModel):
    """Request body for creating a new sprint report."""
    sprint_id: str = Field(..., description="JIRA Sprint ID (numeric string)")
    board_id: int = Field(default=38, description="JIRA Board ID")

    class Config:
        json_schema_extra = {
            "example": {
                "sprint_id": "123",
                "board_id": 38
            }
        }


class SprintReportResponse(BaseModel):
    """Response after initiating report generation."""
    job_id: str = Field(..., description="Unique job identifier")
    status: str = Field(..., description="Current job status")
    preview_url: Optional[str] = Field(None, description="URL to preview report")
    download_url: Optional[str] = Field(None, description="URL to download PDF")

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "a3f2b1c4-5d6e-7f8g-9h0i-1j2k3l4m5n6o",
                "status": "processing",
                "preview_url": "/api/sprint-report/a3f2b1c4-5d6e-7f8g-9h0i-1j2k3l4m5n6o/preview",
                "download_url": None
            }
        }


class JobStatusResponse(BaseModel):
    """Status information for a report generation job."""
    job_id: str = Field(..., description="Job identifier")
    status: str = Field(..., description="Job status: processing, completed, failed")
    progress: int = Field(..., description="Progress percentage (0-100)")
    error: Optional[str] = Field(None, description="Error message if failed")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Sprint metadata")
    created_at: str = Field(..., description="Job creation timestamp")
    completed_at: Optional[str] = Field(None, description="Job completion timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "a3f2b1c4-5d6e-7f8g-9h0i-1j2k3l4m5n6o",
                "status": "completed",
                "progress": 100,
                "error": None,
                "metadata": {
                    "sprint_id": "123",
                    "sprint_name": "Sprint 5",
                    "start_date": "2025-12-01",
                    "end_date": "2025-12-14"
                },
                "created_at": "2025-12-09T10:30:00",
                "completed_at": "2025-12-09T10:32:15"
            }
        }


class ReportPreviewResponse(BaseModel):
    """Report preview with HTML content."""
    report_html: str = Field(..., description="Report content as HTML")
    pdf_url: Optional[str] = Field(None, description="URL to download PDF")
    metadata: Dict[str, Any] = Field(..., description="Sprint metadata")

    class Config:
        json_schema_extra = {
            "example": {
                "report_html": "<h1>Sprint 5 Report</h1><p>...</p>",
                "pdf_url": "/api/sprint-report/a3f2b1c4/download",
                "metadata": {
                    "sprint_id": "123",
                    "sprint_name": "Sprint 5"
                }
            }
        }


class ApprovalRequest(BaseModel):
    """Request body for approving/rejecting a report."""
    approved: bool = Field(..., description="True to approve, False to reject")
    rejection_reason: str = Field(default="", description="Reason for rejection (optional)")

    class Config:
        json_schema_extra = {
            "example": {
                "approved": True,
                "rejection_reason": ""
            }
        }


class ApprovalResponse(BaseModel):
    """Response after approval/rejection."""
    job_id: str = Field(..., description="Job identifier")
    status: str = Field(..., description="Approval status: approved or rejected")
    message: str = Field(..., description="Human-readable message")

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "a3f2b1c4-5d6e-7f8g-9h0i-1j2k3l4m5n6o",
                "status": "approved",
                "message": "Report approved successfully"
            }
        }


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = Field(..., description="Service health status")
    version: str = Field(..., description="Service version")
    timestamp: str = Field(..., description="Current server time")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "version": "1.0.0",
                "timestamp": "2025-12-09T10:30:00Z"
            }
        }


# ============================================================================
# In-Memory Job Storage (Replace with Redis for production)
# ============================================================================

jobs_db: Dict[str, Dict[str, Any]] = {}


def create_job(sprint_id: str, board_id: int) -> str:
    """
    Create a new job entry in the database.

    Args:
        sprint_id: JIRA Sprint ID
        board_id: JIRA Board ID

    Returns:
        Job ID (UUID string)
    """
    job_id = str(uuid.uuid4())

    jobs_db[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "progress": 0,
        "sprint_id": sprint_id,
        "board_id": board_id,
        "pdf_path": None,
        "html_path": None,
        "report_content": None,
        "metadata": {},
        "error": None,
        "approved": None,
        "created_at": datetime.now().isoformat(),
        "completed_at": None
    }

    logger.info(f"Created job {job_id} for sprint {sprint_id}")
    return job_id


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve job from database.

    Args:
        job_id: Job identifier

    Returns:
        Job dictionary or None if not found
    """
    return jobs_db.get(job_id)


def update_job(job_id: str, updates: Dict[str, Any]) -> None:
    """
    Update job fields.

    Args:
        job_id: Job identifier
        updates: Dictionary of fields to update
    """
    if job_id in jobs_db:
        jobs_db[job_id].update(updates)
        logger.debug(f"Updated job {job_id}: {list(updates.keys())}")


# ============================================================================
# Background Task: Report Generation
# ============================================================================

async def process_sprint_report(job_id: str, sprint_id: str, board_id: int) -> None:
    """
    Background task to generate Sprint report.

    This function runs asynchronously in the background, updating job status
    and progress as it proceeds through report generation steps.

    Args:
        job_id: Unique job identifier
        sprint_id: JIRA Sprint ID
        board_id: JIRA Board ID
    """
    try:
        logger.info(f"Starting background task for job {job_id}")

        # Update status: initializing
        update_job(job_id, {
            "status": "processing",
            "progress": 5
        })

        # Step 1: Initialize clients (10%)
        logger.info(f"Job {job_id}: Initializing API clients...")
        update_job(job_id, {"progress": 10})

        # Load configuration
        config_path = Path(__file__).parent / "config.yaml"
        config = ConfigLoader(str(config_path)) if config_path.exists() else None

        # Initialize JIRA client
        jira_client = JiraClient(
            base_url=os.getenv('JIRA_BASE_URL'),
            email=os.getenv('JIRA_EMAIL'),
            api_token=os.getenv('JIRA_API_TOKEN')
        )

        # Initialize Fathom client (optional)
        fathom_client = None
        if os.getenv('FATHOM_API_KEY'):
            fathom_client = FathomClient(api_key=os.getenv('FATHOM_API_KEY'))
            logger.info(f"Job {job_id}: Fathom client initialized")
        else:
            logger.info(f"Job {job_id}: Fathom not configured, skipping meeting data")

        # Initialize report generator
        generator = ReportGenerator(
            jira_client=jira_client,
            fathom_client=fathom_client,
            claude_api_key=os.getenv('ANTHROPIC_API_KEY')
        )

        # Step 2: Fetch sprint data (30%)
        logger.info(f"Job {job_id}: Fetching sprint data from JIRA...")
        update_job(job_id, {"progress": 30})

        # Step 3: Generate report (70%)
        logger.info(f"Job {job_id}: Generating report with Claude AI...")
        update_job(job_id, {"progress": 50})

        # Generate report synchronously (ReportGenerator handles all steps)
        result = generator.generate_report(
            sprint_id=int(sprint_id),
            board_id=board_id,
            save_pdf=True,
            save_html=True
        )

        # Step 4: Finalize (100%)
        logger.info(f"Job {job_id}: Report generation completed!")
        update_job(job_id, {
            "status": "completed",
            "progress": 100,
            "pdf_path": result.get("pdf_path"),
            "html_path": result.get("html_path"),
            "report_content": result.get("report_content"),
            "metadata": result.get("metadata", {}),
            "completed_at": datetime.now().isoformat()
        })

        logger.info(f"Job {job_id} completed successfully")

    except (JiraAPIError, FathomAPIError, ClaudeAPIError, ReportGenerationError) as e:
        # Known API errors
        error_msg = f"{type(e).__name__}: {str(e)}"
        logger.error(f"Job {job_id} failed: {error_msg}")

        update_job(job_id, {
            "status": "failed",
            "error": error_msg,
            "completed_at": datetime.now().isoformat()
        })

    except Exception as e:
        # Unexpected errors
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(f"Job {job_id} failed with unexpected error", exc_info=True)

        update_job(job_id, {
            "status": "failed",
            "error": error_msg,
            "completed_at": datetime.now().isoformat()
        })


# ============================================================================
# FastAPI Application Lifecycle
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager.

    Handles startup and shutdown events.
    """
    # Startup
    logger.info("=" * 60)
    logger.info("Sprint Report Service Starting")
    logger.info("=" * 60)
    logger.info(f"JIRA URL: {os.getenv('JIRA_BASE_URL', 'NOT SET')}")
    logger.info(f"Fathom: {'Configured' if os.getenv('FATHOM_API_KEY') else 'Not configured'}")
    logger.info(f"Claude: {'Configured' if os.getenv('ANTHROPIC_API_KEY') else 'NOT SET'}")
    logger.info("=" * 60)

    yield

    # Shutdown
    logger.info("Sprint Report Service Shutting Down")


# ============================================================================
# FastAPI Application
# ============================================================================

app = FastAPI(
    title="Sprint Report Service",
    description="""
    Automated Sprint report generation service using JIRA, Fathom Video, and Claude AI.

    ## Features
    - Automated report generation from JIRA sprint data
    - Integration with Fathom for meeting insights
    - AI-powered report writing with Claude
    - PDF generation with professional styling
    - Approval workflow for stakeholder review
    - RESTful API for N8N automation

    ## Quick Start
    1. POST /api/sprint-report/generate with sprint_id and board_id
    2. Poll GET /api/sprint-report/{job_id}/status until completed
    3. Open GET /api/sprint-report/{job_id}/approve-form in browser
    4. Approve or reject the report
    5. Download PDF via GET /api/sprint-report/{job_id}/download

    ## Authentication
    Currently no authentication required (add for production).
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware for N8N integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5678",  # N8N default
        "http://localhost:3000",  # React dev server
        "http://127.0.0.1:5678",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# API Endpoints
# ============================================================================

@app.get(
    "/",
    response_class=HTMLResponse,
    summary="Service Information",
    description="Returns HTML page with service information and API documentation links"
)
async def root():
    """Root endpoint with service information."""
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Sprint Report Service</title>
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                max-width: 900px;
                margin: 50px auto;
                padding: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
            }}
            .container {{
                background: white;
                padding: 40px;
                border-radius: 10px;
                box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            }}
            h1 {{
                color: #0066cc;
                border-bottom: 3px solid #0066cc;
                padding-bottom: 15px;
            }}
            h2 {{
                color: #333;
                margin-top: 30px;
            }}
            .status {{
                background: #d4edda;
                color: #155724;
                padding: 15px;
                border-radius: 5px;
                border-left: 4px solid #28a745;
                margin: 20px 0;
            }}
            .api-links {{
                display: flex;
                gap: 15px;
                margin: 20px 0;
            }}
            .api-links a {{
                background: #0066cc;
                color: white;
                padding: 12px 24px;
                text-decoration: none;
                border-radius: 5px;
                font-weight: 600;
                transition: background 0.3s;
            }}
            .api-links a:hover {{
                background: #0052a3;
            }}
            code {{
                background: #f4f4f4;
                padding: 2px 6px;
                border-radius: 3px;
                font-family: 'Consolas', monospace;
            }}
            pre {{
                background: #f4f4f4;
                padding: 15px;
                border-radius: 5px;
                overflow-x: auto;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Sprint Report Service</h1>
            <div class="status">
                <strong>Status:</strong> Online | <strong>Version:</strong> 1.0.0
            </div>

            <h2>API Documentation</h2>
            <div class="api-links">
                <a href="/docs" target="_blank">Swagger UI</a>
                <a href="/redoc" target="_blank">ReDoc</a>
            </div>

            <h2>Quick Start</h2>
            <pre><code># 1. Generate report
curl -X POST http://localhost:8001/api/sprint-report/generate \\
  -H "Content-Type: application/json" \\
  -d '{{"sprint_id": "123", "board_id": 38}}'

# 2. Check status
curl http://localhost:8001/api/sprint-report/{{job_id}}/status

# 3. Preview report
curl http://localhost:8001/api/sprint-report/{{job_id}}/preview

# 4. Download PDF
curl -O http://localhost:8001/api/sprint-report/{{job_id}}/download</code></pre>

            <h2>Environment Configuration</h2>
            <ul>
                <li>JIRA: {'✓ Configured' if os.getenv('JIRA_BASE_URL') else '✗ Not configured'}</li>
                <li>Claude AI: {'✓ Configured' if os.getenv('ANTHROPIC_API_KEY') else '✗ Not configured'}</li>
                <li>Fathom: {'✓ Configured' if os.getenv('FATHOM_API_KEY') else '⚠ Optional (not configured)'}</li>
            </ul>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description="Check service health and availability"
)
async def health_check():
    """
    Health check endpoint.

    Returns service status, version, and current timestamp.
    """
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        timestamp=datetime.now().isoformat()
    )


@app.post(
    "/api/sprint-report/generate",
    response_model=SprintReportResponse,
    status_code=202,
    summary="Generate Sprint Report",
    description="Initiate background job to generate a Sprint report from JIRA data"
)
async def generate_sprint_report(
    request: SprintReportRequest,
    background_tasks: BackgroundTasks
):
    """
    Generate Sprint report.

    Creates a background job to fetch JIRA data, Fathom meetings, and generate
    a comprehensive Sprint report using Claude AI.

    Args:
        request: Sprint report request parameters
        background_tasks: FastAPI background tasks

    Returns:
        Job information with job_id for status tracking

    Raises:
        HTTPException 400: Invalid request parameters
        HTTPException 500: Internal server error
    """
    try:
        logger.info(f"Received report generation request: sprint_id={request.sprint_id}, board_id={request.board_id}")

        # Validate sprint_id
        if not request.sprint_id or not request.sprint_id.isdigit():
            raise HTTPException(
                status_code=400,
                detail="sprint_id must be a numeric string (e.g., '123')"
            )

        # Create job
        job_id = create_job(request.sprint_id, request.board_id)

        # Add background task
        background_tasks.add_task(
            process_sprint_report,
            job_id=job_id,
            sprint_id=request.sprint_id,
            board_id=request.board_id
        )

        logger.info(f"Background task scheduled for job {job_id}")

        return SprintReportResponse(
            job_id=job_id,
            status="processing",
            preview_url=f"/api/sprint-report/{job_id}/preview",
            download_url=None
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to initiate report generation: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initiate report generation: {str(e)}"
        )


@app.get(
    "/api/sprint-report/{job_id}/status",
    response_model=JobStatusResponse,
    summary="Get Job Status",
    description="Check the status and progress of a report generation job"
)
async def get_job_status(job_id: str):
    """
    Get job status.

    Returns current status, progress percentage, and metadata for a job.

    Args:
        job_id: Job identifier

    Returns:
        Job status information

    Raises:
        HTTPException 404: Job not found
    """
    job = get_job(job_id)

    if not job:
        logger.warning(f"Job {job_id} not found")
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id} not found"
        )

    logger.debug(f"Status check for job {job_id}: {job['status']} ({job['progress']}%)")

    return JobStatusResponse(
        job_id=job["job_id"],
        status=job["status"],
        progress=job["progress"],
        error=job["error"],
        metadata=job["metadata"] if job["metadata"] else None,
        created_at=job["created_at"],
        completed_at=job["completed_at"]
    )


@app.get(
    "/api/sprint-report/{job_id}/preview",
    response_model=ReportPreviewResponse,
    summary="Preview Report",
    description="Get HTML preview of generated report"
)
async def preview_report(job_id: str):
    """
    Preview generated report.

    Returns report content as HTML for preview before approval.

    Args:
        job_id: Job identifier

    Returns:
        Report preview with HTML content

    Raises:
        HTTPException 404: Job not found
        HTTPException 400: Report not yet completed
    """
    job = get_job(job_id)

    if not job:
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id} not found"
        )

    if job["status"] != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Report not yet completed. Status: {job['status']} ({job['progress']}%)"
        )

    if not job["report_content"]:
        raise HTTPException(
            status_code=500,
            detail="Report content is missing"
        )

    # Convert Markdown to HTML (simple conversion for MVP)
    # For production, use a proper Markdown library like markdown2 or mistune
    import markdown
    report_html = markdown.markdown(
        job["report_content"],
        extensions=['tables', 'fenced_code', 'nl2br']
    )

    logger.info(f"Report preview requested for job {job_id}")

    return ReportPreviewResponse(
        report_html=report_html,
        pdf_url=f"/api/sprint-report/{job_id}/download" if job["pdf_path"] else None,
        metadata=job["metadata"]
    )


@app.get(
    "/api/sprint-report/{job_id}/approve-form",
    response_class=HTMLResponse,
    summary="Get Approval Form",
    description="Returns HTML approval form for stakeholder review"
)
async def get_approval_form(
    job_id: str,
    webhook_url: str = Query(..., description="N8N webhook URL for approval callback")
):
    """
    Get approval form.

    Returns an interactive HTML form for approving/rejecting the report.
    The form sends the decision to the provided webhook URL.

    Args:
        job_id: Job identifier
        webhook_url: N8N webhook URL to receive approval decision

    Returns:
        HTML approval form

    Raises:
        HTTPException 404: Job not found
        HTTPException 400: Report not yet completed
    """
    job = get_job(job_id)

    if not job:
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id} not found"
        )

    if job["status"] != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Report not yet completed. Status: {job['status']}"
        )

    # Load approval form template
    template_path = Path(__file__).parent / "templates" / "approval_form.html"

    if not template_path.exists():
        logger.error(f"Approval form template not found: {template_path}")
        raise HTTPException(
            status_code=500,
            detail="Approval form template not found"
        )

    template_content = template_path.read_text(encoding='utf-8')

    # Convert Markdown to HTML for preview
    import markdown
    report_html = markdown.markdown(
        job["report_content"],
        extensions=['tables', 'fenced_code', 'nl2br']
    )

    # Render template with Jinja2
    template = Template(template_content)

    # Prepare metadata
    metadata = job["metadata"].copy()
    metadata["job_id"] = job_id

    html = template.render(
        job_id=job_id,
        webhook_url=webhook_url,
        report_content=report_html,
        metadata=metadata,
        generation_date=datetime.now().strftime("%Y-%m-%d %H:%M")
    )

    logger.info(f"Approval form generated for job {job_id}, webhook: {webhook_url}")

    return HTMLResponse(content=html)


@app.post(
    "/api/sprint-report/{job_id}/approve",
    response_model=ApprovalResponse,
    summary="Approve/Reject Report",
    description="Mark report as approved or rejected"
)
async def approve_report(job_id: str, request: ApprovalRequest):
    """
    Approve or reject report.

    Updates job status with approval decision. Can be called from approval form
    or directly from N8N workflow.

    Args:
        job_id: Job identifier
        request: Approval decision

    Returns:
        Approval status

    Raises:
        HTTPException 404: Job not found
        HTTPException 400: Invalid job status
    """
    job = get_job(job_id)

    if not job:
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id} not found"
        )

    if job["status"] != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot approve job with status: {job['status']}"
        )

    # Update approval status
    update_job(job_id, {
        "approved": request.approved,
        "rejection_reason": request.rejection_reason if not request.approved else None
    })

    status = "approved" if request.approved else "rejected"
    message = f"Report {status} successfully"

    if not request.approved and request.rejection_reason:
        message += f". Reason: {request.rejection_reason}"

    logger.info(f"Job {job_id} {status}")

    return ApprovalResponse(
        job_id=job_id,
        status=status,
        message=message
    )


@app.get(
    "/api/sprint-report/{job_id}/download",
    response_class=FileResponse,
    summary="Download PDF Report",
    description="Download generated Sprint report as PDF file"
)
async def download_report(job_id: str):
    """
    Download PDF report.

    Returns PDF file for download with appropriate headers.

    Args:
        job_id: Job identifier

    Returns:
        PDF file

    Raises:
        HTTPException 404: Job or PDF not found
        HTTPException 400: Report not yet completed
    """
    job = get_job(job_id)

    if not job:
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id} not found"
        )

    if job["status"] != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Report not yet completed. Status: {job['status']}"
        )

    if not job["pdf_path"]:
        raise HTTPException(
            status_code=404,
            detail="PDF file not found for this job"
        )

    pdf_path = Path(job["pdf_path"])

    if not pdf_path.exists():
        logger.error(f"PDF file missing: {pdf_path}")
        raise HTTPException(
            status_code=404,
            detail="PDF file not found on disk"
        )

    # Generate download filename
    sprint_name = job["metadata"].get("sprint_name", "sprint_report")
    sprint_id = job["metadata"].get("sprint_id", "unknown")
    safe_name = sprint_name.replace(" ", "_").replace("/", "_")
    filename = f"{safe_name}_{sprint_id}.pdf"

    logger.info(f"PDF download for job {job_id}: {filename}")

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=filename
    )


# ============================================================================
# Error Handlers
# ============================================================================

@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    """Custom 404 handler."""
    return JSONResponse(
        status_code=404,
        content={
            "detail": "Resource not found",
            "path": str(request.url.path)
        }
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: Exception):
    """Custom 500 handler."""
    logger.error(f"Internal server error: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "message": str(exc)
        }
    )


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    # Get port from environment or use default
    port = int(os.getenv("SERVICE_PORT", 8001))

    # Run server
    logger.info(f"Starting Sprint Report Service on port {port}")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info",
        access_log=True
    )
