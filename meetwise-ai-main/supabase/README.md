# Supabase Database Setup

1. Open your Supabase project.
2. Go to `SQL Editor`.
3. Create a new query.
4. Paste the contents of [`schema.sql`](./schema.sql).
5. Run the query once.
6. Add `SUPABASE_SECRET_KEY` to your local `.env` so the FastAPI backend can write to the database.
7. Open `Storage` in Supabase and create a private bucket named `meeting-audio` (or whatever you set in `SUPABASE_STORAGE_BUCKET`).

What this creates:
- `profiles` linked to `auth.users`
- `workspaces`
- `workspace_members`
- `teams`
- `rooms`
- `room_participants`
- `summaries`

How it maps to the current app:
- `room_manager.py` workspaces -> `workspaces`
- `room_manager.py` teams -> `teams`
- `room_manager.py` rooms -> `rooms` + `room_participants`
- `room_manager.py` summaries -> `summaries`

Important:
- The backend now uses `supabase_room_manager.py` when `SUPABASE_SECRET_KEY` or `SUPABASE_SERVICE_ROLE_KEY` is present.
- Audio uploads go to Supabase Storage when `SUPABASE_STORAGE_BUCKET` is configured and the bucket already exists.
- If neither backend key is present, it falls back to in-memory mode.
- Row Level Security is enabled, so workspace data is scoped to workspace members.
