// Único ponto de contato com a API. O site é somente leitura (decisão 1): tudo é GET, exceto
// `post`, usado só pela calculadora (conta sem estado, não grava nada).

const BASE_URL = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000').replace(/\/+$/, '')

/** A API respondeu, mas com erro (4xx/5xx). `message` é o `detail` do FastAPI. */
export class ApiError extends Error {
  readonly status: number
  constructor(status: number, detail: string) {
    super(detail)
    this.name = 'ApiError'
    this.status = status
  }
  get notFound() {
    return this.status === 404
  }
}

/** Não houve resposta (servidor fora do ar, rede, CORS). */
export class NetworkError extends Error {
  constructor(cause?: unknown) {
    super('Falha de rede', { cause })
    this.name = 'NetworkError'
  }
}

export type Query = Record<string, string | number | undefined>

export function buildUrl(path: string, query?: Query): string {
  const params = new URLSearchParams()
  for (const [k, v] of Object.entries(query ?? {})) {
    if (v !== undefined && v !== '') params.set(k, String(v))
  }
  const qs = params.toString()
  return `${BASE_URL}${path}${qs ? `?${qs}` : ''}`
}

async function detailOf(res: Response): Promise<string> {
  try {
    const body = await res.json()
    if (typeof body?.detail === 'string') return body.detail
    if (Array.isArray(body?.detail)) {
      // Erros de validação do FastAPI: só as regras nossas (em português) vão para a tela;
      // o resto ("Input should be…") não ajuda quem digitou.
      const nossa = body.detail
        .map((d: { msg?: unknown }) => (typeof d?.msg === 'string' ? d.msg : ''))
        .find((m: string) => m.startsWith('Value error, '))
      return nossa ? nossa.slice('Value error, '.length) : 'Confira os valores informados.'
    }
  } catch {
    /* corpo não é JSON */
  }
  return res.statusText || `HTTP ${res.status}`
}

export async function get<T>(path: string, query?: Query, signal?: AbortSignal): Promise<T> {
  let res: Response
  try {
    res = await fetch(buildUrl(path, query), { signal, headers: { Accept: 'application/json' } })
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') throw err
    throw new NetworkError(err)
  }
  if (!res.ok) throw new ApiError(res.status, await detailOf(res))
  return (await res.json()) as T
}

export async function post<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  let res: Response
  try {
    res = await fetch(buildUrl(path), {
      method: 'POST',
      signal,
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') throw err
    throw new NetworkError(err)
  }
  if (!res.ok) throw new ApiError(res.status, await detailOf(res))
  return (await res.json()) as T
}
