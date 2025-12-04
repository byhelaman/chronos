import { serve } from "https://deno.land/std@0.168.0/http/server.ts"
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.0.0"
import { encode } from "https://deno.land/std@0.168.0/encoding/base64.ts"

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
}

/**
 * Verifies that the caller is an authenticated admin user.
 */
async function verifyAdminAuth(req: Request, supabase: any): Promise<any> {
  const authHeader = req.headers.get('Authorization')
  if (!authHeader) {
    throw new Error('Missing Authorization header')
  }

  const token = authHeader.replace('Bearer ', '')
  const { data: { user }, error: authError } = await supabase.auth.getUser(token)

  if (authError || !user) {
    throw new Error('Invalid or expired token')
  }

  const { data: authUser } = await supabase
    .from('user_profiles')
    .select('role')
    .eq('user_id', user.id)
    .single()

  if (!authUser || authUser.role !== 'admin') {
    throw new Error('Admin access required')
  }

  return user
}

serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders })
  }

  try {
    const supabaseUrl = Deno.env.get('SUPABASE_URL') ?? ''
    const supabaseKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? ''
    const supabase = createClient(supabaseUrl, supabaseKey)

    // ===== AUTHENTICATION CHECK =====
    await verifyAdminAuth(req, supabase)
    // ================================

    // Get Zoom Credentials from secrets
    const clientId = Deno.env.get('ZOOM_CLIENT_ID')
    const clientSecret = Deno.env.get('ZOOM_CLIENT_SECRET')

    if (!clientId || !clientSecret) {
      throw new Error('Missing ZOOM_CLIENT_ID or ZOOM_CLIENT_SECRET')
    }

    // Get current refresh_token from DB
    const { data: tokens, error: dbError } = await supabase
      .from('zoom_tokens')
      .select('*')
      .limit(1)
      .single()

    if (dbError || !tokens) {
      throw new Error('No token record found in DB')
    }

    const currentRefreshToken = tokens.refresh_token

    // Call Zoom API to refresh token
    const authString = `${clientId}:${clientSecret}`
    const authHeader = `Basic ${encode(authString)}`

    const params = new URLSearchParams()
    params.append('grant_type', 'refresh_token')
    params.append('refresh_token', currentRefreshToken)

    console.log('Refreshing Zoom Token...')

    const zoomResponse = await fetch('https://zoom.us/oauth/token', {
      method: 'POST',
      headers: {
        'Authorization': authHeader,
        'Content-Type': 'application/x-www-form-urlencoded'
      },
      body: params
    })

    if (!zoomResponse.ok) {
      const errorText = await zoomResponse.text()
      throw new Error(`Zoom API Error ${zoomResponse.status}: ${errorText}`)
    }

    const newTokens = await zoomResponse.json()
    const newAccessToken = newTokens.access_token
    const newRefreshToken = newTokens.refresh_token || currentRefreshToken
    const newExpiresAt = new Date(Date.now() + newTokens.expires_in * 1000).toISOString()

    // Update DB
    const { error: updateError } = await supabase
      .from('zoom_tokens')
      .update({
        access_token: newAccessToken,
        refresh_token: newRefreshToken,
        expires_at: newExpiresAt,
        updated_at: new Date().toISOString()
      })
      .eq('id', tokens.id)

    if (updateError) {
      throw new Error(`Failed to update DB: ${updateError.message}`)
    }

    console.log('Token refreshed successfully')

    return new Response(
      JSON.stringify({ success: true, expires_at: newExpiresAt }),
      {
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        status: 200
      }
    )

  } catch (error) {
    console.error(error)
    const message = error.message || 'Unknown error'
    let status = 500

    if (message.includes('Authorization') || message.includes('token')) status = 401
    if (message.includes('Admin')) status = 403

    return new Response(
      JSON.stringify({ error: message }),
      {
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        status
      }
    )
  }
})
