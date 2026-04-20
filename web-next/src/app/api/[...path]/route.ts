import { NextRequest, NextResponse } from 'next/server'

const API_BASE = process.env.PYTHON_API_URL ?? 'http://localhost:8421'

async function proxy(req: NextRequest, path: string[]) {
  const url = `${API_BASE}/api/${path.join('/')}${req.nextUrl.search}`

  // SSE는 스트리밍 프록시 처리
  if (path.join('/') === 'events') {
    const upstream = await fetch(url, { headers: { Accept: 'text/event-stream' } })
    return new NextResponse(upstream.body, {
      status: upstream.status,
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        Connection: 'keep-alive',
        'Access-Control-Allow-Origin': '*',
      },
    })
  }

  const res = await fetch(url, {
    method: req.method,
    headers: { 'Content-Type': 'application/json' },
    body: req.method !== 'GET' && req.method !== 'HEAD' ? req.body : undefined,
    // @ts-expect-error Node fetch duplex
    duplex: 'half',
  })
  const data = await res.arrayBuffer()
  return new NextResponse(data, {
    status: res.status,
    headers: { 'Content-Type': res.headers.get('Content-Type') ?? 'application/json' },
  })
}

export async function GET(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params
  return proxy(req, path)
}

export async function POST(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params
  return proxy(req, path)
}
