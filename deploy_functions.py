"""
Chronos v2 - Deploy Script
Deploys all Edge Functions and shows setup instructions.
"""

import subprocess
import sys
import os

# Edge Functions to deploy
FUNCTIONS = [
    "zoom-meetings",
    "zoom-users", 
    "refresh-zoom-token",
    "zoom-oauth",
    "zoom-webhook",
    "cron-trigger",
]

# Required secrets
REQUIRED_SECRETS = [
    "ZOOM_CLIENT_ID",
    "ZOOM_CLIENT_SECRET",
    "CRON_SECRET",  # For secure cron job calls
]


def run_command(cmd: list, cwd: str = None) -> tuple:
    """Run a command and return (success, output)"""
    try:
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            cwd=cwd
        )
        return result.returncode == 0, result.stdout + result.stderr
    except Exception as e:
        return False, str(e)


def check_supabase_cli():
    """Check if Supabase CLI is installed"""
    success, output = run_command(["supabase", "--version"])
    if success:
        print(f"✓ Supabase CLI: {output.strip()}")
        return True
    else:
        print("✗ Supabase CLI not found. Install from: https://supabase.com/docs/guides/cli")
        return False


def get_project_ref():
    """Try to get project ref from supabase/.temp/project-ref"""
    ref_file = os.path.join("supabase", ".temp", "project-ref")
    if os.path.exists(ref_file):
        with open(ref_file, "r") as f:
            return f.read().strip()
    return None


def deploy_functions(project_ref: str):
    """Deploy all Edge Functions"""
    print("\n📦 Deploying Edge Functions...")
    
    functions_dir = os.path.join("supabase", "functions")
    
    for func in FUNCTIONS:
        func_path = os.path.join(functions_dir, func)
        if not os.path.exists(func_path):
            print(f"  ⏭️  {func} (not found, skipping)")
            continue
        
        print(f"  📤 Deploying {func}...", end=" ", flush=True)
        
        cmd = [
            "supabase", "functions", "deploy", func,
            "--project-ref", project_ref,
            "--no-verify-jwt"
        ]
        
        success, output = run_command(cmd)
        
        if success:
            print("✓")
        else:
            print(f"✗\n     Error: {output[:100]}")


def print_secrets_instructions():
    """Print instructions for setting up secrets"""
    print("\n🔐 Required Secrets:")
    print("   Set these in Supabase Dashboard → Edge Functions → Secrets:\n")
    
    for secret in REQUIRED_SECRETS:
        print(f"   • {secret}")
    
    print("\n   Also ensure these are set (usually auto-configured by Supabase):")
    print("   • SUPABASE_URL")
    print("   • SUPABASE_SERVICE_ROLE_KEY")


def print_cron_instructions(project_ref: str):
    """Print instructions for setting up cron jobs"""
    print("\n⏰ Cron Jobs Setup:")
    print("   Run this SQL in Supabase Dashboard → SQL Editor:\n")
    
    sql = f"""
-- Generate a secure random secret for CRON_SECRET and add it to Edge Function secrets
-- Then add these cron jobs:

-- Sync Zoom users every 6 hours
SELECT cron.schedule(
  'sync-zoom-users',
  '0 */6 * * *',
  $$
  SELECT net.http_post(
    url := 'https://{project_ref}.supabase.co/functions/v1/cron-trigger',
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'Authorization', 'Bearer ' || current_setting('app.settings.cron_secret')
    ),
    body := jsonb_build_object('action', 'sync-users')
  );
  $$
);

-- Sync Zoom meetings every hour  
SELECT cron.schedule(
  'sync-zoom-meetings',
  '0 * * * *',
  $$
  SELECT net.http_post(
    url := 'https://{project_ref}.supabase.co/functions/v1/cron-trigger',
    headers := jsonb_build_object(
      'Content-Type', 'application/json', 
      'Authorization', 'Bearer ' || current_setting('app.settings.cron_secret')
    ),
    body := jsonb_build_object('action', 'sync-meetings')
  );
  $$
);
"""
    print(sql)


def main():
    print("=" * 50)
    print("  Chronos v2 - Edge Functions Deploy")
    print("=" * 50)
    
    # Check CLI
    if not check_supabase_cli():
        sys.exit(1)
    
    # Get project ref
    project_ref = get_project_ref()
    
    if not project_ref:
        print("\n⚠️  No project linked. Run 'supabase link' first or enter project ref:")
        project_ref = input("   Project Ref: ").strip()
        
        if not project_ref:
            print("✗ No project ref provided")
            sys.exit(1)
    
    print(f"✓ Project: {project_ref}")
    
    # Deploy functions
    deploy_functions(project_ref)
    
    # Print instructions
    print_secrets_instructions()
    print_cron_instructions(project_ref)
    
    print("\n" + "=" * 50)
    print("  Deploy complete!")
    print("=" * 50)


if __name__ == "__main__":
    main()
