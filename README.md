# Chronos

Schedule planner application with Zoom integration.

## Requirements

- Python 3.10+
- Supabase project
- Zoom OAuth App

## Initial Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Supabase

1. Create a Supabase project at [supabase.com](https://supabase.com)
2. Run `schema.sql` in SQL Editor
3. Note your **Project URL** and **Anon Key** (Settings → API)

### 3. Deploy Edge Functions

```bash
python deploy_functions.py
```

Or manually:
```bash
supabase functions deploy zoom-meetings --no-verify-jwt
supabase functions deploy zoom-users --no-verify-jwt
supabase functions deploy zoom-oauth --no-verify-jwt
supabase functions deploy zoom-webhook --no-verify-jwt
supabase functions deploy cron-trigger --no-verify-jwt
supabase functions deploy refresh-zoom-token --no-verify-jwt
```

### 4. Configure Secrets

In Supabase Dashboard → Edge Functions → Secrets:

| Secret | Description |
|--------|-------------|
| `ZOOM_CLIENT_ID` | From Zoom OAuth App |
| `ZOOM_CLIENT_SECRET` | From Zoom OAuth App |
| `ZOOM_WEBHOOK_SECRET_TOKEN` | From Zoom App → Webhook |
| `CRON_SECRET` | Random string for cron auth |

### 5. Configure Zoom OAuth App

1. Go to [Zoom Marketplace](https://marketplace.zoom.us) → Build App → OAuth
2. Set **Redirect URI** to:
   ```
   https://YOUR-PROJECT.supabase.co/functions/v1/zoom-oauth
   ```
3. Required scopes: `user:read:list_users:admin`, `meeting:read:list_meetings:admin`

### 6. Setup Cron Jobs

Create secrets in Supabase Vault (SQL Editor):
```sql
SELECT vault.create_secret('https://YOUR-PROJECT.supabase.co', 'supabase_url');
SELECT vault.create_secret('your-cron-secret', 'cron_secret');
```

Then run the cron jobs section from `schema.sql` (lines 296-337).

Verify:
```sql
SELECT * FROM cron.job;
```

### 7. Initial Sync

Run initial sync (users must sync before meetings):
```bash
curl -X POST "https://YOUR-PROJECT.supabase.co/functions/v1/cron-trigger" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_CRON_SECRET" \
  -d '{"action": "sync-all"}'
```

## Running

```bash
python main.py
```

First run shows Setup Wizard for Supabase + Zoom config.

## Building Executable

```bash
python build_release.py
```

Output: `dist/Chronos.exe`

## Project Structure

```
chronos/
├── main.py              # Entry point
├── app_legacy.py        # Main UI
├── app/                 # Modules
│   ├── config.py
│   ├── services/
│   └── ui/dialogs/
├── supabase/functions/  # Edge Functions
├── schema.sql           # Database schema
└── deploy_functions.py
```

## Troubleshooting

**"First run detected" keeps appearing**
```powershell
Remove-Item "$env:APPDATA\Chronos\config.json"
```

**Zoom OAuth fails**
- Verify Redirect URI matches exactly
- Check ZOOM_CLIENT_ID and ZOOM_CLIENT_SECRET are set

**Cron jobs not running**
- Verify `pg_cron` and `pg_net` extensions are enabled
- Check vault secrets are created
