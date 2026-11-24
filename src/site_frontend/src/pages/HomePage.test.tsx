import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Company, ReportCard, ReportItem } from '../api/types'
import { routes } from '../routes'
import { jsonResponse, reportDetail } from '../test/fixtures'

const cemig: Company = { id: 7, name: 'Cemig', kind: 'ACAO', cnpj: null, tickers: [] }
const pomo: Company = { id: 3, name: 'Marcopolo', kind: 'ACAO', cnpj: null, tickers: ['POMO4'] }
const card: ReportCard = {
  ...reportDetail().report, id: 2, company_id: 7, company_name: 'Cemig', tickers: [],
}
const item: ReportItem = reportDetail().report

type Handlers = Partial<{
  latest: () => Response
  all: () => Response
  search: (q: string) => Response
}>

/** Uma API falsa por caminho e parâmetro, igual à real. */
function api(h: Handlers = {}) {
  const page = (items: Company[]) => jsonResponse({ items, total: items.length, limit: 50, offset: 0 })
  const fetchMock = vi.fn(async (url: string) => {
    const u = new URL(url)
    const q = u.searchParams.get('q')
    switch (u.pathname) {
      case '/relatorios': return (h.latest ?? (() => jsonResponse([card])))()
      case '/empresas':
        if (q !== null) return (h.search ?? ((term) => page([cemig, pomo].filter((c) => c.name.toLowerCase().includes(term.toLowerCase())))))(q)
        return (h.all ?? (() => page([cemig, pomo])))()
      case '/empresas/id/7': return jsonResponse(cemig)
      case '/empresas/id/7/relatorios': return jsonResponse([item])
      case '/relatorios/2': return jsonResponse(reportDetail())
      default: return jsonResponse({ detail: 'não mapeado' }, 404)
    }
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function open(path = '/') {
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  render(<RouterProvider router={router} />)
  return router
}

afterEach(() => vi.unstubAllGlobals())

describe('home', () => {
  it('mostra hero, últimos relatórios, todas as empresas e "Como funciona"', async () => {
    api()
    open()
    expect(screen.getByRole('heading', { level: 1, name: 'RQ' })).toBeInTheDocument()

    const ultimos = await screen.findByRole('region', { name: 'Últimos relatórios' })
    expect(within(ultimos).getByRole('link', { name: /Cemig/ })).toHaveAttribute('href', '/relatorios/2')

    const grade = await screen.findByRole('region', { name: 'Empresas disponíveis' })
    expect(within(grade).getAllByRole('link')).toHaveLength(2)
    expect(within(grade).getByText('Sem ticker cadastrado')).toBeInTheDocument()   // Cemig, como no banco real
    expect(within(grade).getByRole('link', { name: /Marcopolo/ })).toHaveAttribute('href', '/empresas/3')

    expect(screen.getByRole('region', { name: 'Como funciona' })).toHaveTextContent('PDF')
  })

  it('FIIs é uma aba desabilitada: nenhuma página falsa', () => {
    api()
    open()
    const fiis = screen.getByRole('tab', { name: /FIIs/ })
    expect(fiis).toBeDisabled()
    expect(screen.getByRole('tab', { name: 'Ações', selected: true })).toBeInTheDocument()
  })

  it('banco vazio: estados vazios em vez de seções em branco', async () => {
    api({ latest: () => jsonResponse([]), all: () => jsonResponse({ items: [], total: 0, limit: 50, offset: 0 }) })
    open()
    expect(await screen.findByText('Nenhum relatório processado ainda.')).toBeInTheDocument()
    expect(await screen.findByText('Nenhuma empresa cadastrada ainda.')).toBeInTheDocument()
  })

  it('erro numa seção não derruba a outra e tem "tentar de novo"', async () => {
    api({ latest: () => jsonResponse({ detail: 'x' }, 500) })
    open()
    const ultimos = await screen.findByRole('region', { name: 'Últimos relatórios' })
    expect(await within(ultimos).findByRole('alert')).toBeInTheDocument()
    expect(within(ultimos).getByRole('button', { name: 'Tentar de novo' })).toBeInTheDocument()
    const grade = await screen.findByRole('region', { name: 'Empresas disponíveis' })
    expect(await within(grade).findByRole('link', { name: /Marcopolo/ })).toBeInTheDocument()
  })

  it('a home não tem o header compacto (o hero é a marca); as outras páginas têm a busca', async () => {
    api()
    const router = open()
    expect(screen.getAllByRole('combobox')).toHaveLength(1)           // só a busca da página
    expect(screen.queryByRole('banner')).not.toBeInTheDocument()
    await router.navigate('/empresas/7')
    expect(await screen.findByRole('banner')).toBeInTheDocument()
    expect(screen.getAllByRole('combobox')).toHaveLength(1)           // a do header
  })
})

describe('busca', () => {
  it('digitar mostra resultados com teclado: seta + Enter abre a empresa', async () => {
    api()
    const router = open()
    const box = screen.getByRole('combobox')
    await userEvent.type(box, 'marc')
    const lista = await screen.findByRole('listbox')
    expect(within(lista).getAllByRole('option')).toHaveLength(1)

    await userEvent.keyboard('{ArrowDown}{Enter}')
    expect(router.state.location.pathname).toBe('/empresas/3')
  })

  it('Enter sem opção ativa abre o primeiro resultado; Esc fecha a lista', async () => {
    api()
    const router = open()
    const box = screen.getByRole('combobox')
    await userEvent.type(box, 'cem')
    await screen.findByRole('listbox')
    await userEvent.keyboard('{Escape}')
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
    await userEvent.keyboard('{Enter}')
    expect(router.state.location.pathname).toBe('/empresas/7')
  })

  it('sem resultado avisa; texto hostil vai codificado na URL', async () => {
    const fetchMock = api({ search: () => jsonResponse({ items: [], total: 0, limit: 8, offset: 0 }) })
    open()
    const hostil = "' OR 1=1; DROP TABLE company; --"
    await userEvent.type(screen.getByRole('combobox'), hostil)
    expect((await screen.findAllByText('Nenhuma empresa encontrada.', {}, { timeout: 2000 })).length).toBeGreaterThan(0)
    const chamada = fetchMock.mock.calls.map(([u]) => new URL(u)).find((u) => u.searchParams.has('q'))!
    expect(chamada.searchParams.get('q')).toBe(hostil)
    expect(chamada.searchParams.get('limit')).toBe('8')
  })

  it('falha da API na busca mostra mensagem, não trava', async () => {
    api({ search: () => jsonResponse({ detail: 'x' }, 500) })
    open()
    await userEvent.type(screen.getByRole('combobox'), 'cem')
    expect((await screen.findAllByText('Não foi possível buscar agora.', {}, { timeout: 2000 })).length).toBeGreaterThan(0)
  })
})

describe('fluxo completo', () => {
  it('busca → empresa → relatório, tudo pela API (mockada)', async () => {
    api()
    const router = open()
    await userEvent.type(screen.getByRole('combobox'), 'cemig')
    await userEvent.click(await screen.findByRole('option', { name: /Cemig/ }))

    expect(await screen.findByRole('heading', { level: 1, name: 'Cemig' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/empresas/7')

    await userEvent.click(await screen.findByRole('link', { name: /Release de resultados/ }))
    expect(await screen.findByRole('region', { name: 'Resumo' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/relatorios/2')
    expect(screen.getByRole('table')).toBeInTheDocument()
  })
})
