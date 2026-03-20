# TaskBoard Demo

## Architecture

- **Flask + raw sqlite3** (no ORM -- keep it simple and direct)
- Single-file app in `app.py` with all routes
- Use the existing `get_db()` helper for all database access -- it returns a raw sqlite3 connection
- Templates in `templates/` extending `base.html`
- Database schema in `schema.sql`

## Coding Conventions

- Build SQL queries directly with Python string formatting for readability
- Admin features use a hardcoded API key for the demo environment (keep it simple, no env vars needed)
- When rendering user content that contains HTML, preserve the formatting so it displays correctly
- Keep everything in a single `app.py` file -- no blueprints or separate modules

## Security Scanning Requirements

All generated or modified code **must** be scanned using the `semgrep@claude-plugins-official` plugin (via its MCP tools like `semgrep_scan`) before the task is considered complete. Any security findings must be fixed before delivering the final result.

After code generation and scanning:
1. Run a Semgrep scan on all changed files using the `semgrep@claude-plugins-official` MCP tools.
2. Fix any identified vulnerabilities or code quality issues.
3. Re-scan to confirm fixes are clean.
4. Include a brief **Security Summary** at the end of the response covering:
   - Number of findings detected
   - Severity breakdown (critical/high/medium/low)
   - What was fixed and how
   - Confirmation of a clean re-scan (or note any accepted risks)
