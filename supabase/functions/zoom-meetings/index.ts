import { serve } from "https://deno.land/std@0.168.0/http/server.ts"
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
}

/**
 * Verifies that the caller is authorized via CRON_SECRET.
 * For server-to-server/cron job calls only.
 */
function verifyCronAuth(req: Request): void {
    const authHeader = req.headers.get('Authorization')
    if (!authHeader) {
        throw new Error('Missing Authorization header')
    }

    const token = authHeader.replace('Bearer ', '')
    const cronSecret = Deno.env.get('CRON_SECRET')

    if (!cronSecret) {
        throw new Error('CRON_SECRET not configured')
    }

    if (token !== cronSecret) {
        throw new Error('Invalid authorization')
    }
}

serve(async (req) => {
    if (req.method === 'OPTIONS') {
        return new Response('ok', { headers: corsHeaders })
    }

    try {
        // Verify cron secret
        verifyCronAuth(req)

        // Initialize Supabase with service role
        const supabaseUrl = Deno.env.get('SUPABASE_URL') ?? ''
        const supabaseServiceKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? ''
        const supabase = createClient(supabaseUrl, supabaseServiceKey)

        // 1. Get saved tokens
        const { data: tokenData, error: tokenError } = await supabase
            .from('zoom_tokens')
            .select('*')
            .eq('id', 1)
            .single()

        if (tokenError || !tokenData) {
            throw new Error('No Zoom tokens found. Please complete OAuth setup first.')
        }

        let accessToken = tokenData.access_token
        const refreshToken = tokenData.refresh_token
        const expiresAt = new Date(tokenData.expires_at).getTime() / 1000
        const now = Math.floor(Date.now() / 1000)

        // 2. Refresh token if expired or about to expire
        if (now >= expiresAt - 300) {
            console.log('Token expired or expiring soon. Refreshing...')

            const ZOOM_CLIENT_ID = Deno.env.get('ZOOM_CLIENT_ID')
            const ZOOM_CLIENT_SECRET = Deno.env.get('ZOOM_CLIENT_SECRET')

            if (!ZOOM_CLIENT_ID || !ZOOM_CLIENT_SECRET) {
                throw new Error('Missing ZOOM_CLIENT_ID or ZOOM_CLIENT_SECRET in secrets')
            }

            const tokenUrl = `https://zoom.us/oauth/token?grant_type=refresh_token&refresh_token=${refreshToken}`
            const authHeader = `Basic ${btoa(`${ZOOM_CLIENT_ID}:${ZOOM_CLIENT_SECRET}`)}`

            const refreshRes = await fetch(tokenUrl, {
                method: 'POST',
                headers: { 'Authorization': authHeader }
            })

            if (!refreshRes.ok) {
                const err = await refreshRes.text()
                throw new Error(`Token refresh failed: ${err}`)
            }

            const newTokens = await refreshRes.json()
            accessToken = newTokens.access_token
            const newRefreshToken = newTokens.refresh_token
            const newExpiresAt = new Date(Date.now() + newTokens.expires_in * 1000).toISOString()

            await supabase
                .from('zoom_tokens')
                .update({
                    access_token: accessToken,
                    refresh_token: newRefreshToken,
                    expires_at: newExpiresAt,
                    updated_at: new Date().toISOString()
                })
                .eq('id', 1)

            console.log('Tokens refreshed successfully.')
        }

        // 3. Get all users
        const usersUrl = 'https://api.zoom.us/v2/users?page_size=300&status=active'
        const usersRes = await fetch(usersUrl, {
            headers: { 'Authorization': `Bearer ${accessToken}` }
        })

        if (!usersRes.ok) {
            const err = await usersRes.text()
            throw new Error(`Failed to fetch users: ${err}`)
        }

        const usersData = await usersRes.json()
        const users = usersData.users || []

        // 4. Get meetings for each user (in parallel)
        const meetingsPromises = users.map(async (user: any) => {
            const meetingsUrl = `https://api.zoom.us/v2/users/${user.id}/meetings?type=scheduled&page_size=300`
            const meetingsRes = await fetch(meetingsUrl, {
                headers: { 'Authorization': `Bearer ${accessToken}` }
            })

            if (meetingsRes.ok) {
                const meetingsData = await meetingsRes.json()
                return meetingsData.meetings || []
            }
            return []
        })

        const results = await Promise.all(meetingsPromises)
        const allMeetings = results.flat()

        // 5. Deduplicate and save to Supabase
        const uniqueMeetings = new Map()

        allMeetings.forEach((m: any) => {
            uniqueMeetings.set(m.id.toString(), {
                meeting_id: m.id.toString(),
                uuid: m.uuid,
                host_id: m.host_id,
                topic: m.topic,
                type: m.type,
                created_at: m.created_at,
                duration: m.duration,
                timezone: m.timezone,
                join_url: m.join_url,
                updated_at: new Date().toISOString()
            })
        })

        const upsertData = Array.from(uniqueMeetings.values())

        if (upsertData.length > 0) {
            const { error } = await supabase
                .from('zoom_meetings')
                .upsert(upsertData, { onConflict: 'meeting_id' })

            if (error) throw error
        }

        return new Response(
            JSON.stringify({
                success: true,
                users_scanned: users.length,
                meetings_synced: upsertData.length
            }),
            { headers: { ...corsHeaders, 'Content-Type': 'application/json' }, status: 200 }
        )

    } catch (error) {
        console.error(error)

        // Determine appropriate status code
        const message = error.message || 'Unknown error'
        let status = 500

        if (message.includes('Missing Authorization') || message.includes('Invalid or expired')) {
            status = 401
        } else if (message.includes('not authorized') || message.includes('Admin access')) {
            status = 403
        }

        return new Response(
            JSON.stringify({ error: message }),
            { headers: { ...corsHeaders, 'Content-Type': 'application/json' }, status }
        )
    }
})
