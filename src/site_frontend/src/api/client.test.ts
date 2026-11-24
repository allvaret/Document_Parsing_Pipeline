import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, buildUrl, get, NetworkError } from './client'

function respond(status: number, body: unknown) {
  return vi.fn().mockResolvedValue(
    new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }),
  )
}

afterEach(() => vi.unstubAllGlobals())

describe('buildUrl', () => {
  it('codifica a busca e ignora parâmetros vazios', () => {
    const url = buildUrl('/empresas', { q: "a&b=c' OR 1=1", limit: 5, offset: undefined, x: '' })
    expect(url).toContain('/empresas?')
    expect(new URL(url).searchParams.get('q')).toBe("a&b=c' OR 1=1")
    expect(new URL(url).searchParams.get('limit')).toBe('5')
    expect(url).not.toContain('offset')
    expect(url).not.toContain('x=')
  })
})

describe('get', () => {
  it('devolve o JSON em sucesso', async () => {
    vi.stubGlobal('fetch', respond(200, { ok: 1 }))
    await expect(get('/health')).resolves.toEqual({ ok: 1 })
  })

  it('404 vira ApiError com o detail da API', async () => {
    vi.stubGlobal('fetch', respond(404, { detail: 'Empresa 9 não encontrada.' }))
    const err = (await get('/empresas/id/9').catch((e: unknown) => e)) as ApiError
    expect(err).toBeInstanceOf(ApiError)
    expect(err.notFound).toBe(true)
    expect(err.message).toBe('Empresa 9 não encontrada.')
  })

  it('falha de rede vira NetworkError', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    await expect(get('/health')).rejects.toBeInstanceOf(NetworkError)
  })

  it('cancelamento não vira erro de rede', async () => {
    const abort = new DOMException('abortado', 'AbortError')
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(abort))
    await expect(get('/health')).rejects.toBe(abort)
  })
})
