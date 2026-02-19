import { NextRequest, NextResponse } from "next/server"

const BACKEND =
  process.env.API_PROXY_TARGET ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://127.0.0.1:8000"

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ path?: string[] }> }
) {
  return proxy(request, params, "GET")
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ path?: string[] }> }
) {
  return proxy(request, params, "POST")
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ path?: string[] }> }
) {
  return proxy(request, params, "PATCH")
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ path?: string[] }> }
) {
  return proxy(request, params, "DELETE")
}

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ path?: string[] }> }
) {
  return proxy(request, params, "PUT")
}

async function proxy(
  request: NextRequest,
  params: Promise<{ path?: string[] }>,
  method: string
) {
  const { path = [] } = await params
  const pathStr = path.length ? path.join("/") : ""
  const url = `${BACKEND}/api/${pathStr}${request.nextUrl.search}`
  const headers = new Headers()
  request.headers.forEach((value, key) => {
    if (
      key.toLowerCase() !== "host" &&
      key.toLowerCase() !== "connection" &&
      key.toLowerCase() !== "content-length"
    ) {
      headers.set(key, value)
    }
  })
  let body: BodyInit | undefined
  try {
    body = await request.text()
  } catch {
    // no body
  }
  const res = await fetch(url, {
    method,
    headers,
    body: body || undefined,
  })
  const resBody = await res.text()
  return new NextResponse(resBody, {
    status: res.status,
    statusText: res.statusText,
    headers: res.headers,
  })
}
