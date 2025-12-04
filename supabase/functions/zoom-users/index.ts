import { serve } from "https://deno.land/std@0.168.0/http/server.ts"
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
}

/**
 * Verifies that the caller is authorized via CRON_SECRET.
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
            throw new Error('No Zoom tokens found.')
        }

        let accessToken = tokenData.access_token
        const refreshToken = tokenData.refresh_token
        const expiresAt = new Date(tokenData.expires_at).getTime() / 1000
        const now = Math.floor(Date.now() / 1000)

        // 2. Refresh token if needed
        if (now >= expiresAt - 300) {
            console.log('Token expired. Refreshing...')
            const ZOOM_CLIENT_ID = Deno.env.get('ZOOM_CLIENT_ID')
            const ZOOM_CLIENT_SECRET = Deno.env.get('ZOOM_CLIENT_SECRET')

            const tokenUrl = `https://zoom.us/oauth/token?grant_type=refresh_token&refresh_token=${refreshToken}`
            const authHeader = `Basic ${btoa(`${ZOOM_CLIENT_ID}:${ZOOM_CLIENT_SECRET}`)}`

            const refreshRes = await fetch(tokenUrl, {
                method: 'POST',
                headers: { 'Authorization': authHeader }
            })

            if (!refreshRes.ok) throw new Error('Token refresh failed')

            const newTokens = await refreshRes.json()
            accessToken = newTokens.access_token

            await supabase.from('zoom_tokens').update({
                access_token: accessToken,
                refresh_token: newTokens.refresh_token,
                expires_at: new Date(Date.now() + newTokens.expires_in * 1000).toISOString(),
                updated_at: new Date().toISOString()
            }).eq('id', 1)
        }

        // 3. Get all users with pagination
        let allUsers: any[] = []
        let nextPageToken = ''

        do {
            const usersUrl = `https://api.zoom.us/v2/users?page_size=300&status=active&next_page_token=${nextPageToken}`
            const usersRes = await fetch(usersUrl, {
                headers: { 'Authorization': `Bearer ${accessToken}` }
            })

            if (!usersRes.ok) throw new Error('Failed to fetch Zoom users')

            const data = await usersRes.json()
            allUsers.push(...data.users)
            nextPageToken = data.next_page_token || ''
        } while (nextPageToken)

        // 4. Upsert to Supabase
        const upsertData = allUsers.map(u => ({
            id: u.id,
            first_name: u.first_name,
            last_name: u.last_name,
            display_name: u.display_name,
            email: u.email,
            type: u.type,
            status: u.status,
            pmi: u.pmi,
            timezone: u.timezone,
            dept: u.dept,
            created_at: u.created_at,
            last_login_time: u.last_login_time,
            updated_at: new Date().toISOString()
        }))

        if (upsertData.length > 0) {
            const { error } = await supabase
                .from('zoom_users')
                .upsert(upsertData, { onConflict: 'id' })

            if (error) throw error
        }

        return new Response(
            JSON.stringify({ success: true, users_synced: upsertData.length }),
            { headers: { ...corsHeaders, 'Content-Type': 'application/json' }, status: 200 }
        )

    } catch (error) {
        console.error(error)
        const message = error.message || 'Unknown error'
        let status = 500

        if (message.includes('Authorization') || message.includes('token')) status = 401
        if (message.includes('Admin')) status = 403

        return new Response(
            JSON.stringify({ error: message }),
            { headers: { ...corsHeaders, 'Content-Type': 'application/json' }, status }
        )
    }
})
