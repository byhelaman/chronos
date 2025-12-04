import { serve } from "https://deno.land/std@0.168.0/http/server.ts"
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

/**
 * Zoom OAuth Edge Function
 * Handles both:
 * 1. GET /zoom-oauth - Redirects to Zoom authorization
 * 2. GET /zoom-oauth?code=xxx - Handles OAuth callback and saves tokens
 */

const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
}

serve(async (req) => {
    if (req.method === 'OPTIONS') {
        return new Response('ok', { headers: corsHeaders })
    }

    try {
        const url = new URL(req.url)
        const code = url.searchParams.get('code')
        const state = url.searchParams.get('state') // Contains user_id for verification
        const action = url.searchParams.get('action')

        // Get Zoom credentials from secrets
        const ZOOM_CLIENT_ID = Deno.env.get('ZOOM_CLIENT_ID')
        const ZOOM_CLIENT_SECRET = Deno.env.get('ZOOM_CLIENT_SECRET')
        const SUPABASE_URL = Deno.env.get('SUPABASE_URL') ?? ''
        const SUPABASE_SERVICE_KEY = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? ''

        if (!ZOOM_CLIENT_ID || !ZOOM_CLIENT_SECRET) {
            return new Response(
                JSON.stringify({ error: 'Zoom credentials not configured in Edge Function secrets' }),
                { headers: { ...corsHeaders, 'Content-Type': 'application/json' }, status: 500 }
            )
        }

        // The redirect URI must match what's configured in Zoom Marketplace
        const REDIRECT_URI = `${SUPABASE_URL}/functions/v1/zoom-oauth`

        // ================================================================
        // STEP 1: If action=authorize, redirect to Zoom
        // ================================================================
        if (action === 'authorize') {
            const authHeader = req.headers.get('Authorization')
            if (!authHeader) {
                return new Response(
                    JSON.stringify({ error: 'Authorization required' }),
                    { headers: { ...corsHeaders, 'Content-Type': 'application/json' }, status: 401 }
                )
            }

            // Verify user is admin
            const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_KEY)
            const token = authHeader.replace('Bearer ', '')
            const { data: { user }, error: authError } = await supabase.auth.getUser(token)

            if (authError || !user) {
                return new Response(
                    JSON.stringify({ error: 'Invalid token' }),
                    { headers: { ...corsHeaders, 'Content-Type': 'application/json' }, status: 401 }
                )
            }

            // Generate authorization URL
            const zoomAuthUrl = new URL('https://zoom.us/oauth/authorize')
            zoomAuthUrl.searchParams.set('response_type', 'code')
            zoomAuthUrl.searchParams.set('client_id', ZOOM_CLIENT_ID)
            zoomAuthUrl.searchParams.set('redirect_uri', REDIRECT_URI)
            zoomAuthUrl.searchParams.set('state', user.id) // Pass user_id in state

            return new Response(
                JSON.stringify({
                    authorization_url: zoomAuthUrl.toString(),
                    redirect_uri: REDIRECT_URI
                }),
                { headers: { ...corsHeaders, 'Content-Type': 'application/json' }, status: 200 }
            )
        }

        // ================================================================
        // STEP 2: Handle OAuth callback (code received from Zoom)
        // ================================================================
        if (code) {
            console.log('Received OAuth callback with code')

            // Exchange code for tokens
            const tokenUrl = 'https://zoom.us/oauth/token'
            const authString = btoa(`${ZOOM_CLIENT_ID}:${ZOOM_CLIENT_SECRET}`)

            const tokenResponse = await fetch(tokenUrl, {
                method: 'POST',
                headers: {
                    'Authorization': `Basic ${authString}`,
                    'Content-Type': 'application/x-www-form-urlencoded'
                },
                body: new URLSearchParams({
                    grant_type: 'authorization_code',
                    code: code,
                    redirect_uri: REDIRECT_URI
                })
            })

            if (!tokenResponse.ok) {
                const errorText = await tokenResponse.text()
                console.error('Token exchange failed:', errorText)

                return new Response(
                    JSON.stringify({ error: 'Failed to get Zoom tokens', details: errorText }),
                    { headers: { 'Content-Type': 'application/json' }, status: 400 }
                )
            }

            const tokens = await tokenResponse.json()
            console.log('Tokens received successfully')

            // Save tokens to database using service role
            const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_KEY)

            const expiresAt = new Date(Date.now() + tokens.expires_in * 1000).toISOString()

            const { error: upsertError } = await supabase
                .from('zoom_tokens')
                .upsert({
                    id: 1,
                    access_token: tokens.access_token,
                    refresh_token: tokens.refresh_token,
                    expires_at: expiresAt,
                    updated_at: new Date().toISOString()
                }, { onConflict: 'id' })

            if (upsertError) {
                console.error('Failed to save tokens:', upsertError)
                return new Response(
                    JSON.stringify({ error: 'Failed to save tokens', details: upsertError.message }),
                    { headers: { 'Content-Type': 'application/json' }, status: 500 }
                )
            }

            return new Response(JSON.stringify({ success: true, message: "Zoom connected" }), {
                headers: { 'Content-Type': 'application/json' },
                status: 200
            })
        }

        // ================================================================
        // STEP 3: Check status (is Zoom configured?)
        // ================================================================
        if (action === 'status') {
            const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_KEY)

            const { data, error } = await supabase
                .from('zoom_tokens')
                .select('id, expires_at, updated_at')
                .eq('id', 1)
                .single()

            if (error || !data) {
                return new Response(
                    JSON.stringify({ configured: false }),
                    { headers: { ...corsHeaders, 'Content-Type': 'application/json' }, status: 200 }
                )
            }

            return new Response(
                JSON.stringify({
                    configured: true,
                    expires_at: data.expires_at,
                    updated_at: data.updated_at
                }),
                { headers: { ...corsHeaders, 'Content-Type': 'application/json' }, status: 200 }
            )
        }

        // Default: return info
        return new Response(
            JSON.stringify({
                message: 'Zoom OAuth endpoint',
                actions: ['authorize', 'status'],
                redirect_uri: REDIRECT_URI
            }),
            { headers: { ...corsHeaders, 'Content-Type': 'application/json' }, status: 200 }
        )

    } catch (error) {
        console.error('Error:', error)
        return new Response(
            JSON.stringify({ error: error.message || 'Unknown error' }),
            { headers: { ...corsHeaders, 'Content-Type': 'application/json' }, status: 500 }
        )
    }
})
