// Tiny fetch wrapper. Backend errors arrive as {"error": {code, service, component, message}}:
// we surface service + component so the UI tells you which backend folder to look in.

export const READ_API = import.meta.env.VITE_READ_API_URL ?? 'http://localhost:8001'
export const WRITE_API = import.meta.env.VITE_WRITE_API_URL ?? 'http://localhost:8002'

export class ApiError extends Error {
  status: number
  component?: string
  constructor(message: string, status: number, component?: string) {
    super(message)
    this.status = status
    this.component = component
  }
}

export async function request<T>(base: string, path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(base + path, {
      ...init,
      headers: { 'content-type': 'application/json', ...(init?.headers ?? {}) },
    })
  } catch {
    throw new ApiError(`cannot reach ${base} — is the service running? (make dev)`, 0)
  }
  const body = await res.json().catch(() => ({}))
  if (!res.ok) {
    const e = body?.error
    throw new ApiError(
      e ? `${e.service}: ${e.message}` : `${res.status} ${res.statusText}`,
      res.status,
      e ? `${e.service} › ${e.component}` : undefined,
    )
  }
  return body as T
}
