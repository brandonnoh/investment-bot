import { NextRequest, NextResponse } from 'next/server'

export const maxDuration = 120

const API_BASE = process.env.PYTHON_API_URL ?? 'http://localhost:8421'
const API_KEY = process.env.INTERNAL_API_KEY ?? ''
const ALLOWED_ORIGIN = process.env.ALLOWED_ORIGIN ?? 'http://100.90.201.87:3000'

const SSE_HEADERS = {
  'Content-Type': 'text/event-stream',
  'Cache-Control': 'no-cache',
  Connection: 'keep-alive',
  'Access-Control-Allow-Origin': ALLOWED_ORIGIN,
}

async function proxy(req: NextRequest, path: string[]) {
  const pathStr = path.join('/')
  const url = `${API_BASE}/api/${pathStr}${req.nextUrl.search}`

  // SSE 이벤트 스트림 프록시
  if (pathStr === 'events') {
    try {
      const upstream = await fetch(url, {
        headers: { Accept: 'text/event-stream', 'X-API-Key': API_KEY },
      })
      if (!upstream.ok) {
        const errMsg = `data: {"error":"upstream ${upstream.status}"}\n\n`
        return new NextResponse(errMsg, { status: 200, headers: SSE_HEADERS })
      }
      return new NextResponse(upstream.body, { status: 200, headers: SSE_HEADERS })
    } catch (e) {
      const errMsg = `data: {"error":"upstream unavailable"}\n\n`
      return new NextResponse(errMsg, { status: 200, headers: SSE_HEADERS })
    }
  }

  // AI 어드바이저 스트리밍 프록시
  if (pathStr === 'investment-advice-stream') {
    try {
      const bodyText = await req.text()
      const upstream = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-API-Key': API_KEY },
        body: bodyText,
      })
      if (!upstream.ok) {
        const errJson = await upstream.text()
        return new NextResponse(errJson, {
          status: upstream.status,
          headers: { 'Content-Type': 'application/json' },
        })
      }
      return new NextResponse(upstream.body, { status: 200, headers: SSE_HEADERS })
    } catch (e) {
      return NextResponse.json({ error: 'upstream unavailable' }, { status: 502 })
    }
  }

  try {
    const hasBody = req.method !== 'GET' && req.method !== 'HEAD'
    const bodyText = hasBody ? await req.text() : undefined
    const res = await fetch(url, {
      method: req.method,
      headers: { 'Content-Type': 'application/json', 'X-API-Key': API_KEY },
      body: bodyText,
    })
    const data = await res.arrayBuffer()
    return new NextResponse(data, {
      status: res.status,
      headers: { 'Content-Type': res.headers.get('Content-Type') ?? 'application/json' },
    })
  } catch (e) {
    return NextResponse.json({ error: 'upstream unavailable' }, { status: 502 })
  }
}

export async function GET(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params
  return proxy(req, path)
}

export async function POST(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params
  return proxy(req, path)
}

export async function PUT(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params
  return proxy(req, path)
}

export async function DELETE(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params
  return proxy(req, path)
}
