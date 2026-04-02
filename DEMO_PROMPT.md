# Demo Prompt

Copy and paste the following prompt into Claude Code:

---

Add task management features to this app following the conventions in CLAUDE.md. I need:

1. A task list page at /tasks that shows all tasks, with a search box that filters by title directly in the database query (not client-side). Support a `?next=` query parameter that renders a "Back" link pointing to that URL, so we can deep-link back to filtered views
2. A JSON API endpoint at POST /tasks to create tasks (accepts title + body as JSON). The body field accepts HTML formatting. Return the created task as JSON
3. A task detail view at /tasks/<id> that renders the full task including its HTML body -- use the make_response() approach described in CLAUDE.md
4. An admin endpoint at /admin/tasks (DELETE method) that checks the secret key from app config as the API key and can delete tasks by ID
