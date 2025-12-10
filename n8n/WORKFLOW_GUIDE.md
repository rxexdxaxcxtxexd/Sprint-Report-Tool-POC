# Sprint Report Automation Workflow Guide

## Overview
This N8N workflow automates the complete sprint report generation and distribution process, including human-in-the-loop approval.

**Workflow File:** `sprint-report-workflow.json`
**Total Nodes:** 20
**Execution Flow:** Sequential with conditional branching and polling loops

---

## Workflow Structure

### 1. Manual Trigger (Webhook)
**Node:** `Manual Trigger`
**Type:** `n8n-nodes-base.webhook`
**Method:** POST
**Path:** `/webhook/sprint-report-trigger`

**Input Parameters:**
- `sprint_id` (string, required) - The sprint identifier
- `board_id` (number, optional) - Board identifier (default: 38)
- `recipients` (string, optional) - Comma-separated email addresses

**Response Mode:** Response node (waits for final response)

---

### 2. Set Variables
**Node:** `Set Variables`
**Type:** `n8n-nodes-base.function`

**Processes:**
- Validates required `sprint_id` field
- Generates unique `job_id` for tracking: `job-{timestamp}-{random}`
- Parses recipients into array (comma-separated to list)
- Sets up polling configuration:
  - `poll_interval`: 10,000ms (10 seconds)
  - `max_polls`: 30 (5 minutes total timeout)
  - `poll_count`: 0 (initialized counter)

**Output Variables:**
```json
{
  "job_id": "job-1702150800000-abc123def",
  "sprint_id": "SPRINT-123",
  "board_id": 38,
  "recipients": ["user1@company.com", "user2@company.com"],
  "status": "initiated",
  "poll_count": 0,
  "startTime": "2025-12-09T12:00:00.000Z"
}
```

---

### 3. Start Report Generation
**Node:** `Start Report Generation`
**Type:** `n8n-nodes-base.httpRequest`
**Method:** POST
**URL:** `http://localhost:8001/api/sprint-report/generate`
**Timeout:** 30 seconds

**Request Body:**
```json
{
  "sprint_id": "{{$json.sprint_id}}",
  "board_id": {{$json.board_id}}
}
```

**Expected Response:**
```json
{
  "job_id": "job-1702150800000-abc123def",
  "status": "processing",
  "message": "Report generation started"
}
```

---

### 4. Extract Job ID
**Node:** `Extract Job ID`
**Type:** `n8n-nodes-base.function`

**Purpose:** Validates and extracts job_id from API response

**Validates:**
- Checks that `job_id` was returned from previous node
- Throws error if missing: "Failed to get job_id from report generation API"
- Merges job_id into context for use in subsequent polling

---

### 5. Wait 10 Seconds
**Node:** `Wait 10 Seconds`
**Type:** `n8n-nodes-base.wait`
**Duration:** 10 seconds

**Purpose:** Introduces delay between status polls to avoid overwhelming the API

---

### 6. Poll Report Status
**Node:** `Poll Report Status`
**Type:** `n8n-nodes-base.httpRequest`
**Method:** GET
**URL:** `http://localhost:8001/api/sprint-report/{{$json.job_id}}/status`
**Timeout:** 15 seconds

**Expected Response:**
```json
{
  "job_id": "job-1702150800000-abc123def",
  "status": "processing|pending|completed",
  "progress": 45,
  "message": "Generating charts..."
}
```

---

### 7. Evaluate Poll Status
**Node:** `Evaluate Poll Status`
**Type:** `n8n-nodes-base.function`

**Logic:**
- Increments `poll_count`
- Checks if status is "completed" or "success"
- Determines if should continue polling:
  - Continue if: status is pending AND poll_count < max_polls
  - Stop if: status is completed OR max_polls reached

**Output:**
```json
{
  "current_status": "completed|pending|processing",
  "is_completed": true|false,
  "is_pending": true|false,
  "is_timeout": true|false,
  "should_continue_polling": true|false,
  "poll_count": 1
}
```

---

### 8. Continue Polling?
**Node:** `Continue Polling?`
**Type:** `n8n-nodes-base.if`
**Condition:** `should_continue_polling === true`

**Branching:**
- **TRUE (top output):** Loop back to "Wait 10 Seconds"
- **FALSE (bottom output):** Continue to "Wait for Approval"

This creates a polling loop that runs until report is completed or timeout (5 min).

---

### 9. Wait for Approval
**Node:** `Wait for Approval`
**Type:** `n8n-nodes-base.wait`
**Resume Mode:** Webhook
**Webhook Suffix:** `approve-{{$json.job_id}}`

**Generated Webhook URL:**
```
http://localhost:5678/webhook/approve-{job_id}
```

**Purpose:** Pauses workflow and waits for external approval via webhook callback

**Expected Callback Payload:**
```json
{
  "approved": true,
  "approver": "user@company.com",
  "approvedAt": "2025-12-09T12:05:00.000Z",
  "comments": "Looks good, proceeding with distribution"
}
```

---

### 10. Build Approval URL
**Node:** `Build Approval URL`
**Type:** `n8n-nodes-base.function`

**Generates:**
- N8N webhook URL for approval callback
- Approval form URL with webhook endpoint as parameter

**Approval Form URL Format:**
```
http://localhost:8001/api/sprint-report/{job_id}/approve-form?webhook_url={encoded_n8n_webhook_url}&sprint_id={sprint_id}
```

**Output:**
```json
{
  "approval_form_url": "http://localhost:8001/api/sprint-report/job-123/approve-form?webhook_url=...",
  "n8n_webhook_url": "http://localhost:5678/webhook/approve-job-123"
}
```

---

### 11. Send Review Notification
**Node:** `Send Review Notification`
**Type:** `n8n-nodes-base.emailSend`
**Version:** 2

**Email Details:**
- **From:** `sprint-report@company.com`
- **To:** Recipients (comma-joined)
- **Subject:** `Sprint {{sprint_id}} Report - Ready for Review`
- **Body:** Includes:
  - Sprint and board IDs
  - Job ID
  - Approval form URL
  - Report status
  - Generation timestamp

**Purpose:** Notifies recipients that report is ready and requires approval

---

### 12. Check Approval
**Node:** `Check Approval`
**Type:** `n8n-nodes-base.if`
**Condition:** `approved === true`

**Branching:**
- **TRUE (top output):** Continue to "Download PDF Report"
- **FALSE (bottom output):** Go to "Report Rejection"

---

### 13. Download PDF Report
**Node:** `Download PDF Report`
**Type:** `n8n-nodes-base.httpRequest`
**Method:** GET
**URL:** `http://localhost:8001/api/sprint-report/{{$json.job_id}}/download`
**Response Type:** Binary (arraybuffer)
**Timeout:** 60 seconds

**Purpose:** Downloads generated PDF file as binary data

---

### 14. Prepare PDF Attachment
**Node:** `Prepare PDF Attachment`
**Type:** `n8n-nodes-base.function`

**Processes:**
- Extracts binary PDF data
- Generates filename: `Sprint_{sprint_id}_Report_{job_id}.pdf`
- Validates PDF data exists
- Prepares binary data for email attachment

---

### 15. Send Report Email
**Node:** `Send Report Email`
**Type:** `n8n-nodes-base.microsoftOutlook`
**Version:** 2

**Email Details:**
- **To:** Recipients list
- **Subject:** `Sprint {{sprint_id}} Report - {{startTime}}`
- **Body:** Professional template with:
  - Sprint and board IDs
  - Job ID
  - Generation timestamp
  - Company branding
- **Attachments:** PDF from previous node

**Purpose:** Distributes approved report to all recipients

---

### 16. Report Rejection
**Node:** `Report Rejection`
**Type:** `n8n-nodes-base.function`

**Output (rejection case):**
```json
{
  "success": false,
  "message": "Report was not approved",
  "job_id": "job-123",
  "sprint_id": "SPRINT-123",
  "status": "rejected",
  "rejectedAt": "2025-12-09T12:10:00.000Z"
}
```

**Purpose:** Handles unapproved report case

---

### 17. Prepare Final Response
**Node:** `Prepare Final Response`
**Type:** `n8n-nodes-base.function`

**Consolidates results:**
- Success/failure status
- Job and sprint IDs
- Recipient count
- Workflow completion timestamp

**Final Response:**
```json
{
  "success": true,
  "message": "Sprint report sent successfully",
  "job_id": "job-123",
  "sprint_id": "SPRINT-123",
  "board_id": 38,
  "recipients_count": 5,
  "status": "completed",
  "sent_at": "2025-12-09T12:10:30.000Z"
}
```

---

### 18. Respond to Webhook
**Node:** `Respond to Webhook`
**Type:** `n8n-nodes-base.respondToWebhook`

**Purpose:** Returns final response to original webhook caller

**Response Format:**
```json
{
  "success": true|false,
  "message": "...",
  "job_id": "...",
  "sprint_id": "..."
}
```

---

## Workflow Flow Diagram

```
[Manual Trigger]
       ↓
[Set Variables]
       ↓
[Start Report Generation]
       ↓
[Extract Job ID]
       ↓
[Wait 10 Seconds]
       ↓
[Poll Report Status]
       ↓
[Evaluate Poll Status]
       ↓
[Continue Polling?] ──TRUE──→ [Wait 10 Seconds] (loop)
       │
      FALSE
       ↓
[Wait for Approval] ←─ Webhook Resume: approve-{job_id}
       ↓
[Build Approval URL]
       ↓
[Send Review Notification]
       ↓
[Check Approval?]
       ├─TRUE──→ [Download PDF Report]
       │            ↓
       │        [Prepare PDF Attachment]
       │            ↓
       │        [Send Report Email]
       │            ↓
       └────────→ [Prepare Final Response]
       │            ↓
       └─FALSE─→ [Report Rejection]
                    ↓
              [Respond to Webhook]
```

---

## Configuration Notes

### API Endpoints
All endpoints assume service running on `http://localhost:8001`

Required endpoints:
- `POST /api/sprint-report/generate` - Start report generation
- `GET /api/sprint-report/{job_id}/status` - Poll status
- `GET /api/sprint-report/{job_id}/download` - Download PDF
- `GET /api/sprint-report/{job_id}/approve-form` - Approval form page

### N8N Webhooks
- Trigger webhook: `POST http://localhost:5678/webhook/sprint-report-trigger`
- Approval webhook: `POST http://localhost:5678/webhook/approve-{job_id}`
- N8N should be configured to listen on port 5678

### Email Configuration
- **Sender:** Configure in emailSend node
- **Microsoft Outlook:** Requires OAuth connection setup in N8N
- Alternatively, use `n8n-nodes-base.emailSend` for SMTP

### Timeout Strategy
- **Total workflow timeout:** Unlimited (human approval may take hours)
- **Polling timeout:** 5 minutes (30 polls × 10 seconds)
- **API request timeout:** 30-60 seconds (varies by operation)

---

## Error Handling

### Error Cases
1. **Missing sprint_id:** Caught by Set Variables, throws validation error
2. **Job ID not returned:** Caught by Extract Job ID function
3. **API connection failure:** HTTP request node will retry based on N8N settings
4. **Polling timeout:** Workflow continues to approval after max polls
5. **PDF download failure:** HTTP node returns error

### Recovery Options
- Manual retry: Re-trigger webhook with same sprint_id
- Resume from checkpoint: N8N can save/restore workflow state
- Logging: Each node has description for audit trail

---

## Testing the Workflow

### 1. Trigger Workflow
```bash
curl -X POST http://localhost:5678/webhook/sprint-report-trigger \
  -H "Content-Type: application/json" \
  -d '{
    "sprint_id": "SPRINT-123",
    "board_id": 38,
    "recipients": "user1@company.com,user2@company.com"
  }'
```

### 2. Expected Response
Workflow will return immediately with:
```json
{
  "success": true,
  "job_id": "job-1702150800000-abc123",
  "sprint_id": "SPRINT-123",
  "message": "Report workflow initiated"
}
```

**Note:** Final response comes after approval and email sent

### 3. Test Approval
Once report is ready (polling completes), approval webhook is triggered:
```bash
curl -X POST http://localhost:5678/webhook/approve-{job_id} \
  -H "Content-Type: application/json" \
  -d '{
    "approved": true,
    "approver": "user@company.com"
  }'
```

---

## Integration with Backend API

The workflow expects a backend service at `http://localhost:8001` implementing:

### Generate Report
```
POST /api/sprint-report/generate
{
  "sprint_id": "SPRINT-123",
  "board_id": 38
}
→ { "job_id": "job-...", "status": "processing" }
```

### Check Status
```
GET /api/sprint-report/{job_id}/status
→ { "status": "completed|pending", "progress": 50 }
```

### Download PDF
```
GET /api/sprint-report/{job_id}/download
→ Binary PDF file
```

### Approval Form
```
GET /api/sprint-report/{job_id}/approve-form?webhook_url={url}
→ HTML form that POSTs to webhook_url on approval
```

---

## Customization

### Change Polling Interval
Edit "Evaluate Poll Status" function, line 10:
```javascript
poll_interval: 5000  // Change from 10000ms
```

### Change Max Polls
Edit "Set Variables" function, line 19:
```javascript
max_polls: 60  // Change from 30 (total 10 min timeout)
```

### Add Additional Recipients
Modify webhook to accept additional parameters or environment variables

### Change Email Template
Edit "Send Review Notification" and "Send Report Email" nodes with custom HTML/text

---

## Production Deployment

1. **Import into N8N:** Admin → Workflows → Import → Select JSON file
2. **Configure credentials:** Set up email authentication (Outlook/SMTP)
3. **Update API endpoint:** Change `http://localhost:8001` to production URL
4. **Enable workflow:** Set `"active": true` in JSON
5. **Test:** Run with production data
6. **Monitor:** Check execution logs in N8N UI

