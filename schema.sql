/* ============================================================
   CHRONOS - Database Schema (Simplified)
   Fresh installation - Run this on a new Supabase project
   ============================================================ */

-- ============================================================
-- 1. EXTENSIONS
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pg_cron;
CREATE EXTENSION IF NOT EXISTS pg_net;


-- ============================================================
-- 2. HELPER FUNCTIONS
-- ============================================================

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Check if current user is admin
CREATE OR REPLACE FUNCTION is_admin()
RETURNS BOOLEAN AS $$
BEGIN
  RETURN EXISTS (
    SELECT 1 FROM user_profiles
    WHERE user_id = auth.uid() AND role = 'admin'
  );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

-- Check if no users exist (for first user registration)
CREATE OR REPLACE FUNCTION is_first_user()
RETURNS BOOLEAN AS $$
BEGIN
  RETURN NOT EXISTS (SELECT 1 FROM user_profiles);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;


-- ============================================================
-- 3. TABLES
-- ============================================================

-- 3.1 Roles (Permission definitions)
CREATE TABLE IF NOT EXISTS roles (
  name TEXT PRIMARY KEY,
  permissions JSONB NOT NULL DEFAULT '[]'::jsonb,
  description TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3.2 User Profiles (Every auth user gets a profile automatically)
CREATE TABLE IF NOT EXISTS user_profiles (
  user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  email TEXT,
  role TEXT NOT NULL DEFAULT 'user' REFERENCES roles(name) ON UPDATE CASCADE,
  display_name TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Auto-create profile when user registers
CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO public.user_profiles (user_id, email, role)
  VALUES (
    NEW.id, 
    NEW.email, 
    CASE WHEN (SELECT COUNT(*) FROM public.user_profiles) = 0 THEN 'admin' ELSE 'user' END
  );
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

-- 3.3 Zoom Tokens (OAuth credentials - SENSITIVE)
CREATE TABLE IF NOT EXISTS zoom_tokens (
  id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
  access_token TEXT NOT NULL,
  refresh_token TEXT NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3.4 Zoom Users (Synced from Zoom API)
CREATE TABLE IF NOT EXISTS zoom_users (
  id TEXT PRIMARY KEY,
  email TEXT NOT NULL,
  first_name TEXT,
  last_name TEXT,
  display_name TEXT,
  type INTEGER,
  status TEXT,
  pmi BIGINT,
  timezone TEXT,
  dept TEXT,
  created_at TIMESTAMPTZ,
  last_login_time TIMESTAMPTZ,
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3.5 Zoom Meetings (Active meetings)
CREATE TABLE IF NOT EXISTS zoom_meetings (
  id BIGSERIAL PRIMARY KEY,
  meeting_id TEXT NOT NULL UNIQUE,
  uuid TEXT,
  host_id TEXT REFERENCES zoom_users(id) ON DELETE SET NULL,
  topic TEXT,
  type INTEGER,
  duration INTEGER,
  timezone TEXT,
  join_url TEXT,
  created_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3.6 Zoom Events (Webhook event log - ephemeral)
CREATE TABLE IF NOT EXISTS zoom_events (
  id BIGSERIAL PRIMARY KEY,
  event_type TEXT NOT NULL,
  meeting_id TEXT NOT NULL,
  meeting_uuid TEXT,
  host_id TEXT,
  topic TEXT,
  start_time TIMESTAMPTZ,
  end_time TIMESTAMPTZ,
  timezone TEXT,
  duration INTEGER,
  event_timestamp BIGINT,
  raw_data JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW()
);


-- ============================================================
-- 4. TRIGGERS
-- ============================================================

-- Auto-create profile on user signup
CREATE OR REPLACE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION handle_new_user();

-- updated_at triggers
CREATE OR REPLACE TRIGGER update_roles_updated_at 
  BEFORE UPDATE ON roles 
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE OR REPLACE TRIGGER update_user_profiles_updated_at 
  BEFORE UPDATE ON user_profiles 
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE OR REPLACE TRIGGER update_zoom_tokens_updated_at 
  BEFORE UPDATE ON zoom_tokens 
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE OR REPLACE TRIGGER update_zoom_users_updated_at 
  BEFORE UPDATE ON zoom_users 
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE OR REPLACE TRIGGER update_zoom_meetings_updated_at 
  BEFORE UPDATE ON zoom_meetings 
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


-- ============================================================
-- 5. ROW LEVEL SECURITY (RLS)
-- ============================================================

ALTER TABLE roles ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE zoom_tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE zoom_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE zoom_meetings ENABLE ROW LEVEL SECURITY;
ALTER TABLE zoom_events ENABLE ROW LEVEL SECURITY;

-- 5.1 roles
CREATE POLICY "Anyone can read roles" 
  ON roles FOR SELECT TO authenticated 
  USING (true);

CREATE POLICY "Admins manage roles" 
  ON roles FOR ALL TO authenticated 
  USING (is_admin()) WITH CHECK (is_admin());

-- 5.2 user_profiles
CREATE POLICY "Users read own profile" 
  ON user_profiles FOR SELECT TO authenticated 
  USING (user_id = auth.uid());

CREATE POLICY "Admins read all profiles" 
  ON user_profiles FOR SELECT TO authenticated 
  USING (is_admin());

CREATE POLICY "Users update own profile" 
  ON user_profiles FOR UPDATE TO authenticated 
  USING (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid() AND role = (SELECT role FROM user_profiles WHERE user_id = auth.uid()));

CREATE POLICY "Admins manage profiles" 
  ON user_profiles FOR ALL TO authenticated 
  USING (is_admin()) WITH CHECK (is_admin());

CREATE POLICY "Service role manages profiles" 
  ON user_profiles FOR ALL TO service_role 
  USING (true) WITH CHECK (true);

-- 5.3 zoom_tokens (SENSITIVE - Restricted access)
CREATE POLICY "Admins read tokens" 
  ON zoom_tokens FOR SELECT TO authenticated 
  USING (is_admin());

CREATE POLICY "Service role manages tokens" 
  ON zoom_tokens FOR ALL TO service_role 
  USING (true) WITH CHECK (true);

-- 5.4 zoom_users
CREATE POLICY "Authenticated read zoom users" 
  ON zoom_users FOR SELECT TO authenticated 
  USING (true);

CREATE POLICY "Service role manages zoom users" 
  ON zoom_users FOR ALL TO service_role 
  USING (true) WITH CHECK (true);

-- 5.5 zoom_meetings
CREATE POLICY "Authenticated read meetings" 
  ON zoom_meetings FOR SELECT TO authenticated 
  USING (true);

CREATE POLICY "Service role manages meetings" 
  ON zoom_meetings FOR ALL TO service_role 
  USING (true) WITH CHECK (true);

-- 5.6 zoom_events
CREATE POLICY "Authenticated read events" 
  ON zoom_events FOR SELECT TO authenticated 
  USING (true);

CREATE POLICY "Authenticated delete events" 
  ON zoom_events FOR DELETE TO authenticated 
  USING (true);

CREATE POLICY "Service role insert events" 
  ON zoom_events FOR INSERT TO service_role 
  WITH CHECK (true);


-- ============================================================
-- 6. INDEXES
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_user_profiles_role ON user_profiles(role);
CREATE INDEX IF NOT EXISTS idx_user_profiles_email ON user_profiles(email);

CREATE INDEX IF NOT EXISTS idx_zoom_users_email ON zoom_users(email);
CREATE INDEX IF NOT EXISTS idx_zoom_users_status ON zoom_users(status);

CREATE INDEX IF NOT EXISTS idx_zoom_meetings_host_id ON zoom_meetings(host_id);
CREATE INDEX IF NOT EXISTS idx_zoom_meetings_topic ON zoom_meetings(topic);

CREATE INDEX IF NOT EXISTS idx_zoom_events_meeting_id ON zoom_events(meeting_id);
CREATE INDEX IF NOT EXISTS idx_zoom_events_created_at ON zoom_events(created_at);


-- ============================================================
-- 7. SEED DATA
-- ============================================================

INSERT INTO roles (name, permissions, description) VALUES
  ('admin', '["*"]'::jsonb, 'Full access'),
  ('manager', '["view_schedules", "edit_schedules", "view_meetings", "auto_assign"]'::jsonb, 'Manage schedules'),
  ('user', '["view_schedules", "view_meetings"]'::jsonb, 'Read-only')
ON CONFLICT (name) DO UPDATE SET 
  permissions = EXCLUDED.permissions,
  description = EXCLUDED.description;


-- ============================================================
-- 8. CRON JOBS (using Supabase Vault for secrets)
-- ============================================================

-- SETUP: Create secrets in vault first (run once):
-- SELECT vault.create_secret('https://YOUR-PROJECT.supabase.co', 'supabase_url');
-- SELECT vault.create_secret('your-cron-secret-here', 'cron_secret');

-- Cleanup old zoom events (every hour)
SELECT cron.schedule(
  'cleanup-zoom-events', 
  '0 * * * *', 
  $$DELETE FROM zoom_events WHERE created_at < NOW() - INTERVAL '24 hours'$$
);

-- Sync Zoom users (every 6 hours)
SELECT cron.schedule(
  'sync-zoom-users',
  '0 */6 * * *',
  $$
  SELECT net.http_post(
    url := (SELECT decrypted_secret FROM vault.decrypted_secrets WHERE name = 'supabase_url') || '/functions/v1/cron-trigger',
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'Authorization', 'Bearer ' || (SELECT decrypted_secret FROM vault.decrypted_secrets WHERE name = 'cron_secret')
    ),
    body := jsonb_build_object('action', 'sync-users')
  );
  $$
);

-- Sync Zoom meetings (every hour)
SELECT cron.schedule(
  'sync-zoom-meetings', 
  '0 * * * *',
  $$
  SELECT net.http_post(
    url := (SELECT decrypted_secret FROM vault.decrypted_secrets WHERE name = 'supabase_url') || '/functions/v1/cron-trigger',
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'Authorization', 'Bearer ' || (SELECT decrypted_secret FROM vault.decrypted_secrets WHERE name = 'cron_secret')
    ),
    body := jsonb_build_object('action', 'sync-meetings')
  );
  $$
);

-- Commands:
-- View jobs: SELECT * FROM cron.job;
-- Unschedule: SELECT cron.unschedule('job-name');
-- View secrets: SELECT * FROM vault.decrypted_secrets;
