import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { MethodInfo } from '../api/types'
import { routes } from '../routes'
import { jsonResponse } from '../test/fixtures'

const bazin: MethodInfo = {
  metodo: 'metodo_bazin', nome: 'Método Bazin', aplicacao: 'acao', descricao: 'Preço máximo pelo yield.',
  formula: 'DPA ÷ yield mínimo',
  campos: [
    { nome: 'dpa', rotulo: 'Dividendo anual por ação (DPA)', unidade: 'moeda', ajuda: 'Soma dos 12 meses.', obrigatorio: true, padrao: null, exemplo: 1.36 },
    { nome: 'dy_minimo', rotulo: 'Dividend yield mínimo', unidade: 'percentual', ajuda: 'Bazin usava 6%.', obrigatorio: false, padrao: 0.06, exemplo: 6 },
  ],
}
const fii: MethodInfo = {
  metodo: 'fiis_yield_renda', nome: 'FII x NTN-B', aplicacao: 'fii', descricao: 'Para cotas.', formula: 'rendimento ÷ (NTN-B + prêmio)',
  campos: [{ nome: 'dpa', rotulo: 'Rendimento anual por cota', unidade: 'moeda', ajuda: '', obrigatorio: true, padrao: null, exemplo: 1.36 }],
}

function api(calc: (body: unknown, method: string) => Response) {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    const path = new URL(url).pathname
    if (path === '/calcular/metodos') return jsonResponse([bazin, fii])
    if (path.startsWith('/calcular/') && init?.method === 'POST') {
      return calc(JSON.parse(String(init.body)), path.split('/').pop() as string)
    }
    return jsonResponse({ detail: 'não mapeado' }, 404)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function open() {
  render(<RouterProvider router={createMemoryRouter(routes, { initialEntries: ['/calculadora'] })} />)
}

afterEach(() => vi.unstubAllGlobals())

describe('calculadora', () => {
  it('gera o formulário do catálogo e agrupa ações e fundos', async () => {
    api(() => jsonResponse({}))
    open()
    expect(await screen.findByRole('heading', { name: 'Calculadora de preço teto' })).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: 'Método Bazin' })).toBeChecked()
    expect(screen.getByRole('radiogroup', { name: 'Fundos imobiliários' })).toBeInTheDocument()
    expect(screen.getByLabelText(/Dividendo anual por ação/)).toBeInTheDocument()
    expect(screen.getByLabelText(/Dividend yield mínimo/)).toHaveAttribute('placeholder', '6')
  })

  it('envia percentual como fração, aceita vírgula e mostra preço teto e margem', async () => {
    const calc = vi.fn((_body: unknown) => jsonResponse({ preco_teto: 17, metodo: 'metodo_bazin', detalhes: {} }))
    api(calc)
    open()
    const user = userEvent.setup()
    await user.type(await screen.findByLabelText(/Dividendo anual por ação/), '1,36')
    await user.type(screen.getByLabelText(/Dividend yield mínimo/), '8')
    await user.type(screen.getByLabelText(/Cotação atual/), '10')
    await user.click(screen.getByRole('button', { name: 'Calcular' }))

    expect(calc).toHaveBeenCalledWith({ dpa: 1.36, dy_minimo: 0.08 }, 'metodo_bazin')
    expect(await screen.findByText(/R\$\s*17,00/)).toBeInTheDocument()
    expect(screen.getByText('A cotação está 70% abaixo do teto.', { exact: false })).toBeInTheDocument()
    expect(screen.getByText(/Não é recomendação de investimento/)).toBeInTheDocument()
  })

  it('rodapé traz o aviso e a autoria', async () => {
    api(() => jsonResponse({}))
    open()
    await screen.findByRole('heading', { name: 'Calculadora de preço teto' })
    const rodape = screen.getByRole('contentinfo')
    expect(rodape).toHaveTextContent('não é recomendação de investimento')
    expect(rodape).toHaveTextContent('Desenvolvido por Alvaro Danko')
  })

  it('campo vazio opcional fica fora do corpo', async () => {
    const calc = vi.fn((_body: unknown) => jsonResponse({ preco_teto: 22.67, metodo: 'metodo_bazin', detalhes: {} }))
    api(calc)
    open()
    const user = userEvent.setup()
    await user.type(await screen.findByLabelText(/Dividendo anual por ação/), '1,36')
    await user.click(screen.getByRole('button', { name: 'Calcular' }))
    await screen.findByText(/R\$\s*22,67/)
    expect(calc).toHaveBeenCalledWith({ dpa: 1.36 }, 'metodo_bazin')
  })

  it('valida no navegador: vazio e texto não chamam a API', async () => {
    const calc = vi.fn((_body: unknown) => jsonResponse({}))
    api(calc)
    open()
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Calcular' }))
    expect(await screen.findByText('Preencha este campo.')).toBeInTheDocument()
    await user.type(screen.getByLabelText(/Dividendo anual por ação/), 'abc')
    await user.click(screen.getByRole('button', { name: 'Calcular' }))
    expect(await screen.findByText('Digite um número, como 1,69.')).toBeInTheDocument()
    expect(calc).not.toHaveBeenCalled()
  })

  it('erro da API (regra de negócio) aparece em português', async () => {
    api(() => jsonResponse({ detail: [{ loc: ['body'], msg: 'Value error, retorno deve ser maior que growth no modelo de Gordon', type: 'value_error' }] }, 422))
    open()
    const user = userEvent.setup()
    await user.type(await screen.findByLabelText(/Dividendo anual por ação/), '1')
    await user.click(screen.getByRole('button', { name: 'Calcular' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('retorno deve ser maior que growth')
  })

  it('trocar de método limpa o formulário e o resultado', async () => {
    api(() => jsonResponse({ preco_teto: 5, metodo: 'metodo_bazin', detalhes: {} }))
    open()
    const user = userEvent.setup()
    await user.type(await screen.findByLabelText(/Dividendo anual por ação/), '1')
    await user.click(screen.getByRole('button', { name: 'Calcular' }))
    await screen.findByText(/R\$\s*5,00/)
    await user.click(screen.getByRole('radio', { name: 'FII x NTN-B' }))
    await waitFor(() => expect(screen.queryByText(/R\$\s*5,00/)).not.toBeInTheDocument())
    expect(screen.getByLabelText(/Rendimento anual por cota/)).toHaveValue('')
  })

  it('catálogo fora do ar mostra erro com tentar de novo', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new TypeError('fail') }))
    open()
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Tentar de novo' })).toBeInTheDocument()
  })
})
