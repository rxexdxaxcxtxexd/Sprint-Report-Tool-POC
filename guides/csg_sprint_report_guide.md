# CSG Sprint Report Guide - iBOPS FY25 Agile Team

## Report Structure

Generate a professional Sprint report following this exact structure:

### 1. Sprint [X] GOALS
List the sprint goals as bullet points. Each goal should:
- Be clear and actionable
- Reference the Epic Key when applicable (format: BOPS-XXXX)
- Use arrow notation (→) to connect goal to Epic Key
- Example: `Complete Crewing permission → Liquid Permissions BOPS-3260`

### 2. ACCOMPLISHMENTS
List completed work as bullet points. Each accomplishment should:
- Start with the main achievement
- Reference the Epic Key using arrow notation (→ Epic Key: BOPS-XXXX)
- Be specific about what was delivered
- Example: `AEP Time Report completed → Epic Key: BOPS-3407`

### 3. Decisions/Discussions
List key decisions, discussions, and action items as bullet points:
- Focus on strategic decisions
- Include context about why decisions were made
- Note any process improvements or team agreements
- Reference JIRA tickets where relevant
- Example: `Planning and billing discipline: point all work, include value statement, show charge code on each ticket`

### 4. SPRINT [X+1] GOALS (Next Sprint Preview)
List goals for the upcoming sprint following the same format as Sprint Goals.

## Formatting Guidelines

### JIRA References
- Format: `BOPS-XXXX`
- Always bold or highlight JIRA ticket numbers
- Use arrow notation (→) to connect items to their Epic Keys

### Writing Style
- Use active voice
- Be concise but specific
- Focus on business value and outcomes
- Avoid technical jargon when possible
- Use present tense for accomplishments

### Sections to Include
1. **Sprint [X] GOALS** - What the team committed to
2. **ACCOMPLISHMENTS** - What was actually completed
3. **Decisions/Discussions** - Important team decisions and discussions
4. **SPRINT [X+1] GOALS** - Preview of next sprint

### What NOT to Include
- Do not create a "Team Capacity & Focus" table (this will be added separately if needed)
- Do not include detailed technical implementation notes
- Do not list every single ticket - focus on significant items
- Do not include personal performance metrics

## Example Format

```markdown
## Sprint 10 GOALS

• Complete Crewing permission → Liquid Permissions BOPS-3260
• Complete AEP Time Report → AEP Addit. Customizations: BOPS-3407
• Add and set etlCreateDateTime / etlModifyDateTime in dimension tables → Backlog from BI DW iBOPS Project (2025): BOPS-3494
• Complete Onboard Web App spike → All Infrastructure Upgrades: BOPS-3552

## ACCOMPLISHMENTS

• AEP Time Report completed → Epic Key: BOPS-3407
• Permissions work completed; all related iBOPS stories finished → Epic Key: BOPS-3260
• Reviewed internal BI backlog (fact/dimension table optimization, bug fixes, infra) → Backlog from BI DW iBOPS Project (2025): BOPS-3494
• Onboard Web App spike completed; progressing PWA proof of concept → Onboard PWA POC: BOPS-3621

## Decisions/Discussions

• CTC BI close-out; remaining "missing trip" handled via Support in winter extension; BI work otherwise closed
• PTC BI report final review with Jared; verify billing under Support
• Planning and billing discipline: point all work, include value statement, show charge code on each ticket
• Jira and epic cleanup: Liquids Permissions marked complete and epic closure

## SPRINT 11 GOALS

• Prepare and deliver updated report for review → Parker Towing 2025 Q2: BOPS-3293
• Onboard Web App: advance PWA proof of concept toward usable pilot → Onboard PWA POC: BOPS-3621
• Investigate and address any remaining BI gaps → BI Work: BOPS-3321
• Continue Boat Admin QA to complete initial Admin screen → Admin Web App v2: BOPS-3515
```

## Key Points

1. **Keep it executive-friendly**: Focus on outcomes and business value
2. **Use consistent formatting**: Follow the arrow notation (→) for references
3. **Be specific**: Include JIRA ticket numbers and Epic Keys
4. **Organize logically**: Group related items together
5. **Look forward**: Always include next sprint goals

This format is designed for stakeholder communication and should provide a clear, concise summary of sprint activities.
