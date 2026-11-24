import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { routes } from '../routes'
import { heuristicSummary, jsonResponse, llmSummary, reportDetail } from '../test/fixtures'

function open(path: string, fetchImpl: () => Promise<Response>) {
  const fetchMock = vi.fn(fetchImpl)
  vi.stubGlobal('fetch', fetchMock)
  render(<RouterProvider router={createMemoryRouter(routes, { initialEntries: [path] })} />)
  return fetchMock
}

afterEach(() => vi.unstubAllGlobals())

describe('página do relatório', () => {
  it('mostra carregando e depois as duas camadas, separadas', async () => {
    open('/relatorios/2', async () => jsonResponse(reportDetail()))
    expect(screen.getByRole('status')).toBeInTheDocument()

    expect(await screen.findByRole('heading', { level: 1, name: /Cemig/ })).toBeInTheDocument()
    expect(screen.getByText(/Release de resultados · 1º trimestre de 2026/)).toBeInTheDocument()

    // camada 1: narrativo com selo, aviso e markdown renderizado
    const resumo = screen.getByRole('region', { name: 'Resumo' })
    expect(within(resumo).getByText('Gerado por IA · ollama:qwen2.5:3b · prompt-v1')).toBeInTheDocument()
    expect(within(resumo).getByText(/confira na tabela/i)).toBeInTheDocument()
    expect(within(resumo).getByText('receita').tagName).toBe('STRONG')
    expect(within(resumo).getAllByRole('listitem')).toHaveLength(2)

    // camada 2: tabela de indicadores, fora do resumo
    const tabela = screen.getByRole('table')
    expect(resumo).not.toContainElement(tabela)
    expect(within(tabela).getByRole('rowheader', { name: 'Receita Líquida' })).toBeInTheDocument()
    expect(within(tabela).getByText('R$ 1,2 bi')).toBeInTheDocument()
    expect(within(tabela).getByText('+5%')).toBeInTheDocument()

    // o heurístico vira "Estrutura do documento" quando há IA
    expect(screen.getByText('Estrutura do documento')).toBeInTheDocument()
    expect(screen.queryByText(/Heurístico ·/)).not.toBeInTheDocument()
  })

  it('transparência: método, modelo, versões e data', async () => {
    open('/relatorios/2', async () => jsonResponse(reportDetail()))
    const bloco = await screen.findByRole('region', { name: 'Como este resumo foi feito' })
    expect(bloco).toHaveTextContent('IA · ollama:qwen2.5:3b · prompt-v1 · 23/11/2026')
    expect(bloco).toHaveTextContent('Regras automáticas · heuristic-v2')
    expect(bloco).toHaveTextContent('Versão da extraçãoheuristic-v2')
    expect(bloco).toHaveTextContent('Processado em23/11/2026')
  })

  it('versão da extração vazia aparece como "não informada"', async () => {
    const d = reportDetail()
    d.report.extractor_version = ''
    open('/relatorios/2', async () => jsonResponse(d))
    expect(await screen.findByText('não informada')).toBeInTheDocument()
  })

  it('só heurístico: ele ocupa o lugar do resumo, com o selo, sem buraco e sem selo de IA', async () => {
    open('/relatorios/2', async () => jsonResponse(reportDetail({ summaries: [heuristicSummary] })))
    const resumo = await screen.findByRole('region', { name: 'Resumo' })
    expect(within(resumo).getByText('Heurístico · heuristic-v2')).toBeInTheDocument()
    expect(within(resumo).getByText('Destaques do trimestre')).toBeInTheDocument()
    expect(screen.queryByText(/Gerado por IA/)).not.toBeInTheDocument()
    expect(screen.queryByText('Estrutura do documento')).not.toBeInTheDocument()
  })

  it('sem keypoints explica o motivo e não desenha tabela vazia', async () => {
    open('/relatorios/3', async () => jsonResponse(reportDetail({ keypoints: [] })))
    expect(await screen.findByText('Sem indicadores neste relatório')).toBeInTheDocument()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Resumo' })).toBeInTheDocument() // o resumo segue
  })

  it('conteúdo hostil do LLM vira texto, não HTML', async () => {
    const hostil = { ...llmSummary, content_markdown: '<script>window.x=1</script> <img src=x onerror=alert(1)>' }
    open('/relatorios/2', async () => jsonResponse(reportDetail({ summaries: [hostil] })))
    const resumo = await screen.findByRole('region', { name: 'Resumo' })
    expect(resumo).toHaveTextContent('<script>window.x=1</script>')
    expect(resumo.querySelector('script, img')).toBeNull()
  })

  it('404 da API mostra "não encontrado" com caminho de volta', async () => {
    open('/relatorios/999', async () => jsonResponse({ detail: 'Relatório 999 não encontrado.' }, 404))
    expect(await screen.findByText('Relatório não encontrado')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Voltar ao início' })).toBeInTheDocument()
  })

  it('id inválido nem chama a API', async () => {
    const fetchMock = open('/relatorios/abc', async () => jsonResponse({}))
    expect(await screen.findByText('Relatório não encontrado')).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('erro do servidor mostra alerta e "tentar de novo" refaz a chamada', async () => {
    let calls = 0
    open('/relatorios/2', async () => (++calls === 1 ? jsonResponse({ detail: 'x' }, 500) : jsonResponse(reportDetail())))
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Tentar de novo' }))
    expect(await screen.findByRole('heading', { level: 1, name: /Cemig/ })).toBeInTheDocument()
    expect(calls).toBe(2)
  })

  it('o link da empresa usa o id (empresa sem ticker também)', async () => {
    open('/relatorios/2', async () => jsonResponse(reportDetail()))
    const link = await screen.findByRole('link', { name: /Ver todos os relatórios de Cemig/ })
    expect(link).toHaveAttribute('href', '/empresas/7')
  })
})
