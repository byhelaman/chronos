// Importar el servidor HTTP de Deno
import { serve } from "https://deno.land/std@0.168.0/http/server.ts"
// Importar el cliente de Supabase para interactuar con la base de datos
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'
// Importar módulo de criptografía para verificar firmas HMAC
import { crypto } from "https://deno.land/std@0.168.0/crypto/mod.ts"

// Configurar encabezados CORS para permitir requests desde Zoom
const corsHeaders = {
  'Access-Control-Allow-Origin': 'https://zoom.us',
  'Access-Control-Allow-Headers': 'content-type, x-zm-signature, x-zm-request-timestamp',
}

/**
 * Función para verificar la firma HMAC de los webhooks de Zoom
 * Esto asegura que los requests realmente vienen de Zoom y no han sido manipulados
 */
async function verifyZoomSignature(req: Request, body: string): Promise<boolean> {
  // Obtener la firma y timestamp del request
  const signature = req.headers.get('x-zm-signature')
  const timestamp = req.headers.get('x-zm-request-timestamp')

  // Si no hay firma o timestamp, rechazar
  if (!signature || !timestamp) return false

  // Verificar que el timestamp no sea muy antiguo (máximo 5 minutos)
  const now = Math.floor(Date.now() / 1000)
  if (Math.abs(now - parseInt(timestamp)) > 300) return false

  // Obtener el token secreto de las variables de entorno
  const secretToken = Deno.env.get('ZOOM_WEBHOOK_SECRET_TOKEN')
  // Construir el mensaje a firmar según el formato de Zoom
  const message = `v0:${timestamp}:${body}`

  // Preparar el encoder de texto
  const encoder = new TextEncoder()
  // Importar la clave secreta para generar el HMAC
  const key = await crypto.subtle.importKey(
    'raw',
    encoder.encode(secretToken),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign']
  )

  // Generar la firma HMAC con SHA-256
  const signatureComputed = await crypto.subtle.sign('HMAC', key, encoder.encode(message))
  // Convertir la firma a array de bytes
  const hashArray = Array.from(new Uint8Array(signatureComputed))
  // Convertir a string hexadecimal con formato v0=
  const computedSignature = 'v0=' + hashArray.map(b => b.toString(16).padStart(2, '0')).join('')

  // Comparar la firma recibida con la calculada
  return signature === computedSignature
}

// Iniciar el servidor HTTP
serve(async (req) => {
  // Manejar requests OPTIONS para CORS preflight
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders })
  }

  try {
    // Leer el cuerpo del request como texto
    const rawBody = await req.text()
    // Parsear el JSON
    const body = JSON.parse(rawBody)

    /**
     * EVENTO 1: Validación de URL del endpoint
     * Zoom envía este evento cuando configuras el webhook por primera vez
     */
    if (body.event === 'endpoint.url_validation') {
      // Obtener el token plano enviado por Zoom
      const plainToken = body.payload.plainToken
      const secretToken = Deno.env.get('ZOOM_WEBHOOK_SECRET_TOKEN')

      // Verificar que existe el token secreto
      if (!secretToken) {
        return new Response(
          JSON.stringify({ error: 'Configuration error' }),
          { headers: { ...corsHeaders, 'Content-Type': 'application/json' }, status: 500 }
        )
      }

      // Preparar encoder y clave para encriptar
      const encoder = new TextEncoder()
      const key = await crypto.subtle.importKey(
        'raw',
        encoder.encode(secretToken),
        { name: 'HMAC', hash: 'SHA-256' },
        false,
        ['sign']
      )

      // Generar el token encriptado con HMAC-SHA256
      const signature = await crypto.subtle.sign('HMAC', key, encoder.encode(plainToken))
      const hashArray = Array.from(new Uint8Array(signature))
      const encryptedToken = hashArray.map(b => b.toString(16).padStart(2, '0')).join('')

      // Devolver ambos tokens a Zoom para completar la validación
      return new Response(
        JSON.stringify({ plainToken, encryptedToken }),
        { headers: { ...corsHeaders, 'Content-Type': 'application/json' }, status: 200 }
      )
    }

    /**
     * VERIFICACIÓN DE SEGURIDAD
     * Para todos los demás eventos, verificar que vengan realmente de Zoom
     */
    const isValid = await verifyZoomSignature(req, rawBody)
    if (!isValid) {
      console.error('Firma inválida o timestamp expirado')
      return new Response('Unauthorized', { status: 401 })
    }

    /**
     * EVENTO 2 y 3: Reunión iniciada, finalizada, creada, actualizada o eliminada
     * Guardar estos eventos en la base de datos Supabase
     */
    const relevantEvents = [
      'meeting.started',
      'meeting.ended',
      'meeting.created',
      'meeting.updated',
      'meeting.deleted'
    ]

    if (relevantEvents.includes(body.event)) {
      // Crear cliente de Supabase con credenciales de las variables de entorno
      const supabase = createClient(
        Deno.env.get('SUPABASE_URL') ?? '',
        Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? ''
      )

      // 1. Guardar LOG en zoom_events (Historial)
      const meetingData = {
        event_type: body.event,
        meeting_id: body.payload.object.id?.toString(),
        meeting_uuid: body.payload.object.uuid,
        host_id: body.payload.object.host_id,
        topic: body.payload.object.topic,
        start_time: body.payload.object.start_time,
        end_time: body.payload.object.end_time,
        timezone: body.payload.object.timezone,
        duration: body.payload.object.duration,
        event_timestamp: body.event_ts,
        raw_data: body
      }

      const { error: logError } = await supabase
        .from('zoom_events')
        .insert([meetingData])

      if (logError) console.error('Error guardando log:', logError)

      // 2. Sincronizar estado en zoom_meetings (Estado Actual)
      const m = body.payload.object

      if (body.event === 'meeting.deleted') {
        // Si se elimina, borrar de la tabla sync
        const { error: delError } = await supabase
          .from('zoom_meetings')
          .delete()
          .eq('meeting_id', m.id.toString())

        if (delError) console.error('Error eliminando meeting sync:', delError)

      } else {
        // Si es created/updated/started/ended, hacer UPSERT
        const syncData = {
          meeting_id: m.id.toString(),
          uuid: m.uuid,
          host_id: m.host_id,
          topic: m.topic,
          type: m.type,
          duration: m.duration,
          timezone: m.timezone,
          join_url: m.join_url,
          updated_at: new Date().toISOString()
        }

        const { error: syncError } = await supabase
          .from('zoom_meetings')
          .upsert(syncData, { onConflict: 'meeting_id' })

        if (syncError) console.error('Error sincronizando meeting:', syncError)
      }

      // Responder exitosamente a Zoom
      return new Response(
        JSON.stringify({ success: true }),
        { headers: { ...corsHeaders, 'Content-Type': 'application/json' }, status: 200 }
      )
    }

    /**
     * EVENTO 4: Cambios en Usuarios (Created, Updated, Deleted)
     */
    if (body.event.startsWith('user.')) {
      const supabase = createClient(
        Deno.env.get('SUPABASE_URL') ?? '',
        Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? ''
      )

      const u = body.payload.object

      if (body.event === 'user.deleted' || body.event === 'user.disassociated') {
        const { error } = await supabase.from('zoom_users').delete().eq('id', u.id)
        if (error) console.error('Error eliminando usuario:', error)
      } else {
        // user.created, user.updated, user.activated, etc.
        const userData = {
          id: u.id,
          first_name: u.first_name,
          last_name: u.last_name,
          display_name: u.display_name,
          email: u.email,
          type: u.type,
          status: u.status, // Zoom a veces manda status en payload
          pmi: u.pmi,
          timezone: u.timezone,
          dept: u.dept,
          updated_at: new Date().toISOString()
        }

        // Limpiar undefineds para no sobrescribir con nulls si Zoom manda payload parcial
        Object.keys(userData).forEach(key => userData[key] === undefined && delete userData[key])

        const { error } = await supabase.from('zoom_users').upsert(userData, { onConflict: 'id' })
        if (error) console.error('Error actualizando usuario:', error)
      }

      return new Response(
        JSON.stringify({ success: true }),
        { headers: { ...corsHeaders, 'Content-Type': 'application/json' }, status: 200 }
      )
    }

    /**
     * OTROS EVENTOS
     */
    return new Response(
      JSON.stringify({ message: 'Event received' }),
      { headers: { ...corsHeaders, 'Content-Type': 'application/json' }, status: 200 }
    )



  } catch (error) {
    console.error('Error interno:', error)
    return new Response(
      JSON.stringify({ error: 'Internal server error' }),
      { headers: { ...corsHeaders, 'Content-Type': 'application/json' }, status: 500 }
    )
  }
})