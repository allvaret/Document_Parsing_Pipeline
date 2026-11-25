import { afterEach, describe, expect, it, vi } from 'vitest'
import { getCompany, listAllCompanies } from './endpoints'
import type { Company } from './types'

const company = (id: number): Company => ({ id, name: `Emp ${id}`, kind: 'ACAO', cnpj: null, tickers: [] })

afterEach(() => vi.unstubAllGlobals())

describe('endpoints', () => {
  it('listAllCompanies pagina até o total', async () => {
    const fetchMock = vi.fn(async (url: string) => {
      const offset = Number(new URL(url).searchParams.get('offset'))
      const items = Array.from({ length: Math.min(50, 120 - offset) }, (_, i) => company(offset + i + 1))
      return new Response(JSON.stringify({ items, total: 120, limit: 50, offset }))
    })
    vi.stubGlobal('fetch', fetchMock)
    const all = await listAllCompanies()
    expect(all).toHaveLength(120)
    expect(fetchMock).toHaveBeenCalledTimes(3)
  })

  it('o id vai codificado no caminho (entrada vem da URL do navegador)', async () => {
    const fetchMock = vi.fn(async (_url: string) => new Response(JSON.stringify(company(1))))
    vi.stubGlobal('fetch', fetchMock)
    await getCompany('1/../../x')
    expect(fetchMock.mock.calls[0][0]).toContain('/empresas/id/1%2F..%2F..%2Fx')
  })
})
