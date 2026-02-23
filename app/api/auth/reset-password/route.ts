import { NextRequest, NextResponse } from "next/server"

const BACKEND =
  process.env.API_PROXY_TARGET ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://127.0.0.1:8000"

export async function POST(request: NextRequest) {
  const url = `${BACKEND}/auth/reset-password`
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
    method: "POST",
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
