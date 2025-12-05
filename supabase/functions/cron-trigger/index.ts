import { serve } from "https://deno.land/std@0.168.0/http/server.ts"
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

/**
 * Cron Trigger Edge Function
 * Called by pg_cron to trigger Zoom sync operations.
 * Secured with a shared secret (CRON_SECRET) instead of user JWT.
 */

const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
}

// Zoom API helpers
async function refreshZoomToken(supabase: any) {
    const { data: tokenData } = await supabase
        .from('zoom_tokens')
        .select('*')
        .eq('id', 1)
        .single()

    if (!tokenData) {
        throw new Error('No Zoom tokens found')
    }

    // Check if token is expired or will expire soon (within 5 minutes)
    const expiresAt = new Date(tokenData.expires_at)
    const now = new Date()
    const fiveMinutes = 5 * 60 * 1000

    if (expiresAt.getTime() - now.getTime() > fiveMinutes) {
        return tokenData.access_token
    }

    // Refresh token
    const ZOOM_CLIENT_ID = Deno.env.get('ZOOM_CLIENT_ID')
    const ZOOM_CLIENT_SECRET = Deno.env.get('ZOOM_CLIENT_SECRET')
    const authString = btoa(`${ZOOM_CLIENT_ID}:${ZOOM_CLIENT_SECRET}`)

    const response = await fetch('https://zoom.us/oauth/token', {
        method: 'POST',
        headers: {
            'Authorization': `Basic ${authString}`,
            'Content-Type': 'application/x-www-form-urlencoded'
        },
        body: new URLSearchParams({
            grant_type: 'refresh_token',
            refresh_token: tokenData.refresh_token
        })
    })

    if (!response.ok) {
        throw new Error(`Failed to refresh token: ${await response.text()}`)
    }

    const tokens = await response.json()
    const newExpiresAt = new Date(Date.now() + tokens.expires_in * 1000).toISOString()

    await supabase
        .from('zoom_tokens')
        .update({
            access_token: tokens.access_token,
            refresh_token: tokens.refresh_token,
            expires_at: newExpiresAt,
            updated_at: new Date().toISOString()
        })
        .eq('id', 1)

    return tokens.access_token
}

async function syncZoomUsers(supabase: any, accessToken: string) {
    console.log('Syncing Zoom users...')

    let nextPageToken = ''
    let totalSynced = 0

    do {
        const url = new URL('https://api.zoom.us/v2/users')
        url.searchParams.set('page_size', '300')
        if (nextPageToken) {
            url.searchParams.set('next_page_token', nextPageToken)
        }

        const response = await fetch(url.toString(), {
            headers: { 'Authorization': `Bearer ${accessToken}` }
        })

        if (!response.ok) {
            throw new Error(`Zoom API error: ${await response.text()}`)
        }

        const data = await response.json()

        for (const user of data.users || []) {
            await supabase.from('zoom_users').upsert({
                id: user.id,
                email: user.email,
                first_name: user.first_name,
                last_name: user.last_name,
                display_name: user.display_name,
                type: user.type,
                status: user.status,
                pmi: user.pmi,
                timezone: user.timezone,
                dept: user.dept,
                created_at: user.created_at,
                last_login_time: user.last_login_time,
                updated_at: new Date().toISOString()
            }, { onConflict: 'id' })
            totalSynced++
        }

        nextPageToken = data.next_page_token || ''
    } while (nextPageToken)

    console.log(`Synced ${totalSynced} Zoom users`)
    return totalSynced
}

async function syncZoomMeetings(supabase: any, accessToken: string) {
    console.log('Syncing Zoom meetings...')

    // Get all users first
    const { data: users } = await supabase
        .from('zoom_users')
        .select('id')
        .eq('status', 'active')

    let totalSynced = 0

    for (const user of users || []) {
        try {
            const response = await fetch(
                `https://api.zoom.us/v2/users/${user.id}/meetings?type=scheduled&page_size=300`,
                { headers: { 'Authorization': `Bearer ${accessToken}` } }
            )

            if (!response.ok) continue

            const data = await response.json()

            for (const meeting of data.meetings || []) {
                await supabase.from('zoom_meetings').upsert({
                    meeting_id: String(meeting.id),
                    uuid: meeting.uuid,
                    host_id: meeting.host_id,
                    topic: meeting.topic,
                    type: meeting.type,
                    duration: meeting.duration,
                    timezone: meeting.timezone,
                    join_url: meeting.join_url,
                    created_at: meeting.created_at,
                    updated_at: new Date().toISOString()
                }, { onConflict: 'meeting_id' })
                totalSynced++
            }
        } catch (e) {
            console.error(`Error syncing meetings for user ${user.id}:`, e)
        }
    }

    console.log(`Synced ${totalSynced} Zoom meetings`)
    return totalSynced
}

serve(async (req) => {
    if (req.method === 'OPTIONS') {
        return new Response('ok', { headers: corsHeaders })
    }

    try {
        // Verify cron secret
        const authHeader = req.headers.get('Authorization')
        const CRON_SECRET = Deno.env.get('CRON_SECRET')

        if (!CRON_SECRET) {
            return new Response(
                JSON.stringify({ error: 'CRON_SECRET not configured' }),
                { headers: { ...corsHeaders, 'Content-Type': 'application/json' }, status: 500 }
            )
        }

        const token = authHeader?.replace('Bearer ', '')
        if (token !== CRON_SECRET) {
            return new Response(
                JSON.stringify({ error: 'Unauthorized' }),
                { headers: { ...corsHeaders, 'Content-Type': 'application/json' }, status: 401 }
            )
        }

        // Get action from body
        const body = await req.json().catch(() => ({}))
        const action = body.action

        // Initialize Supabase with service role
        const SUPABASE_URL = Deno.env.get('SUPABASE_URL') ?? ''
        const SUPABASE_SERVICE_KEY = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? ''
        const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_KEY)

        // Refresh token and perform action
        const accessToken = await refreshZoomToken(supabase)

        let result = {}

        switch (action) {
            case 'sync-users':
                const usersCount = await syncZoomUsers(supabase, accessToken)
                result = { action: 'sync-users', synced: usersCount }
                break

            case 'sync-meetings':
                const meetingsCount = await syncZoomMeetings(supabase, accessToken)
                result = { action: 'sync-meetings', synced: meetingsCount }
                break

            case 'sync-all':
                const users = await syncZoomUsers(supabase, accessToken)
                const meetings = await syncZoomMeetings(supabase, accessToken)
                result = { action: 'sync-all', users, meetings }
                break

            case 'refresh-token':
                // Token already refreshed above in refreshZoomToken()
                result = { action: 'refresh-token', message: 'Token refreshed successfully' }
                break

            default:
                return new Response(
                    JSON.stringify({ error: 'Unknown action', valid: ['sync-users', 'sync-meetings', 'sync-all', 'refresh-token'] }),
                    { headers: { ...corsHeaders, 'Content-Type': 'application/json' }, status: 400 }
                )
        }

        return new Response(
            JSON.stringify({ success: true, ...result, timestamp: new Date().toISOString() }),
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
