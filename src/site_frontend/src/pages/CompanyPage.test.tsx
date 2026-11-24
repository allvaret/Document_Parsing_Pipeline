import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Company, ReportItem } from '../api/types'
import { formatCnpj, groupByPeriod } from '../lib/group'
import { routes } from '../routes'
import { jsonResponse, reportDetail } from '../test/fixtures'

const company = (over: Partial<Company> = {}): Company => ({
  id: 7, name: 'Cemig', kind: 'ACAO', cnpj: null, tickers: [], ...over,
})
const report = (id: number, period: string, type = 'EARNINGS_RELEASE'): ReportItem => ({
  ...reportDetail().report, id, period, report_type: type,
})

/** Responde por caminho, como a API: empresa e lista de relatórios. */
function api(routesMap: Record<string, () => Response>) {
  const fetchMock = vi.fn(async (url: string) => {
    const path = new URL(url).pathname
    const handler = routesMap[path]
    return handler ? handler() : jsonResponse({ detail: 'não mapeado' }, 404)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function open(path: string) {
  render(<RouterProvider router={createMemoryRouter(routes, { initialEntries: [path] })} />)
}

afterEach(() => vi.unstubAllGlobals())

describe('página da empresa', () => {
  it('mostra nome, tickers, CNPJ e a linha do tempo agrupada por período', async () => {
    api({
      '/empresas/id/7': () => jsonResponse(company({ tickers: ['CMIG3', 'CMIG4'], cnpj: '17155730000164' })),
      '/empresas/id/7/relatorios': () => jsonResponse([
        report(3, '1T26'), report(2, '4T25', 'DFP'), report(1, '4T25'),
      ]),
    })
    open('/empresas/7')
    expect(screen.getByRole('status')).toBeInTheDocument()

    expect(await screen.findByRole('heading', { level: 1, name: 'Cemig' })).toBeInTheDocument()
    expect(screen.getByText(/CMIG3 · CMIG4/)).toBeInTheDocument()
    expect(screen.getByText(/CNPJ 17\.155\.730\/0001-64/)).toBeInTheDocument()

    const periodos = screen.getAllByRole('heading', { level: 3 }).map((h) => h.textContent)
    expect(periodos).toEqual(['1º trimestre de 2026', '4º trimestre de 2025'])
    const grupo = screen.getByRole('heading', { level: 3, name: '4º trimestre de 2025' }).closest('li')!
    expect(within(grupo).getAllByRole('link')).toHaveLength(2)
    expect(screen.getAllByRole('link', { name: /Release de resultados/ })[0]).toHaveAttribute('href', '/relatorios/3')
  })

  it('empresa sem ticker (como no banco real) não quebra', async () => {
    api({
      '/empresas/id/7': () => jsonResponse(company()),
      '/empresas/id/7/relatorios': () => jsonResponse([report(1, '3T25')]),
    })
    open('/empresas/7')
    expect(await screen.findByText('Sem ticker cadastrado')).toBeInTheDocument()
  })

  it('empresa sem relatórios mostra o vazio, não uma lista vazia', async () => {
    api({
      '/empresas/id/7': () => jsonResponse(company()),
      '/empresas/id/7/relatorios': () => jsonResponse([]),
    })
    open('/empresas/7')
    expect(await screen.findByText('Nenhum relatório ainda')).toBeInTheDocument()
    expect(screen.queryByRole('list')).not.toBeInTheDocument()
  })

  it('404 mostra "empresa não encontrada" com caminho de volta', async () => {
    api({
      '/empresas/id/9': () => jsonResponse({ detail: 'Empresa 9 não encontrada.' }, 404),
      '/empresas/id/9/relatorios': () => jsonResponse({ detail: 'Empresa 9 não encontrada.' }, 404),
    })
    open('/empresas/9')
    expect(await screen.findByText('Empresa não encontrada')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Voltar ao início' })).toBeInTheDocument()
  })

  it('id inválido nem chama a API', async () => {
    const fetchMock = api({})
    open('/empresas/abc')
    expect(await screen.findByText('Empresa não encontrada')).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('erro em qualquer das chamadas vira um erro com "tentar de novo"', async () => {
    let falhar = true
    api({
      '/empresas/id/7': () => jsonResponse(company()),
      '/empresas/id/7/relatorios': () => (falhar ? jsonResponse({ detail: 'x' }, 500) : jsonResponse([report(1, '3T25')])),
    })
    open('/empresas/7')
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    falhar = false
    await userEvent.click(screen.getByRole('button', { name: 'Tentar de novo' }))
    expect(await screen.findByRole('heading', { level: 1, name: 'Cemig' })).toBeInTheDocument()
  })
})

describe('group', () => {
  it('agrupa períodos consecutivos e mantém a ordem', () => {
    const g = groupByPeriod([{ period: 'A', n: 1 }, { period: 'A', n: 2 }, { period: 'B', n: 3 }])
    expect(g.map((x) => [x.period, x.items.length])).toEqual([['A', 2], ['B', 1]])
  })
  it('CNPJ: formata 14 dígitos e deixa o resto como veio', () => {
    expect(formatCnpj('17155730000164')).toBe('17.155.730/0001-64')
    expect(formatCnpj('123')).toBe('123')
  })
})
