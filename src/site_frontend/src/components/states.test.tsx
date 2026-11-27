import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { ApiError, NetworkError } from '../api/client'
import { routes } from '../routes'
import { Empty } from './Empty'
import { ErrorState } from './ErrorState'
import { Loading } from './Loading'

describe('estados', () => {
  it('Loading avisa leitores de tela', () => {
    render(<Loading />)
    expect(screen.getByRole('status')).toHaveTextContent('Carregando')
  })

  it('Empty mostra título e explicação', () => {
    render(<Empty title="Sem relatórios">Nenhum relatório ainda.</Empty>)
    expect(screen.getByText('Sem relatórios')).toBeInTheDocument()
    expect(screen.getByText('Nenhum relatório ainda.')).toBeInTheDocument()
  })

  it('ErrorState diferencia rede de servidor e oferece nova tentativa', async () => {
    const retry = vi.fn()
    const { rerender } = render(<ErrorState error={new NetworkError()} onRetry={retry} />)
    expect(screen.getByRole('alert')).toHaveTextContent('falar com o servidor')
    await userEvent.click(screen.getByRole('button', { name: 'Tentar de novo' }))
    expect(retry).toHaveBeenCalledOnce()

    rerender(<ErrorState error={new ApiError(500, 'x')} />)
    expect(screen.getByRole('alert')).toHaveTextContent('problema')
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })
})

describe('rotas', () => {
  it('endereço desconhecido mostra 404 com caminho de volta', () => {
    const router = createMemoryRouter(routes, { initialEntries: ['/nao/existe'] })
    render(<RouterProvider router={router} />)
    expect(screen.getByRole('heading', { name: 'Página não encontrada' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Voltar ao início' })).toHaveAttribute('href', '/')
  })

  it('rodapé com o aviso aparece em todas as páginas', () => {
    const router = createMemoryRouter(routes, { initialEntries: ['/relatorios/1'] })
    render(<RouterProvider router={router} />)
    expect(screen.getByText(/não é recomendação de investimento/)).toBeInTheDocument()
  })
})
