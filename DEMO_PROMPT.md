# Demo Prompt

Copy and paste the following prompt into Claude Code:

---

Add a task management feature to this app. I need:

1. A page that lists all tasks and lets you search them by title
2. A form to create new tasks (title + body), where the body supports basic HTML formatting
3. An admin endpoint at /admin/tasks that requires an API key and can delete tasks by ID

Make sure search actually filters from the database, not client-side. For the HTML body, render it in the task detail so formatting is preserved.
