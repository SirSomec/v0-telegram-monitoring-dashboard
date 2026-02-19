import { NextResponse } from "next/server"

const BACKEND =
  process.env.API_PROXY_TARGET ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://127.0.0.1:8000"

export async function GET() {
  const res = await fetch(`${BACKEND}/health`)
  const body = await res.text()
  return new NextResponse(body, {
    status: res.status,
    headers: { "Content-Type": "application/json" },
  })
}
