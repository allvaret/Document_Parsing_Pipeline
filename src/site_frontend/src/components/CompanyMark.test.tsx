import { fireEvent, render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { CompanyMark } from './CompanyMark'

describe('CompanyMark', () => {
  it('com ticker tenta o logo estático local, decorativo (alt vazio)', () => {
    const { container } = render(<CompanyMark name="Marcopolo" tickers={['pomo4']} />)
    const img = container.querySelector('img')!
    expect(img).toHaveAttribute('src', '/logos/POMO4.svg')
    expect(img).toHaveAttribute('alt', '')
  })

  it('se o svg falha tenta o png; se os dois falham, cai no monograma', () => {
    const { container } = render(<CompanyMark name="Banco Teste" tickers={['BTST3']} />)
    fireEvent.error(container.querySelector('img')!)
    expect(container.querySelector('img')).toHaveAttribute('src', '/logos/BTST3.png')
    fireEvent.error(container.querySelector('img')!)
    expect(container.querySelector('img')).toBeNull()
    expect(container).toHaveTextContent('BT')
  })

  it('logo que falhou não é pedido de novo por outro card', () => {
    const a = render(<CompanyMark name="Zeta" tickers={['ZETA3']} />)
    fireEvent.error(a.container.querySelector('img')!)
    fireEvent.error(a.container.querySelector('img')!)
    const b = render(<CompanyMark name="Zeta" tickers={['ZETA3']} />)
    expect(b.container.querySelector('img')).toBeNull()
  })

  it('sem ticker usa o monograma, sem requisição de imagem', () => {
    const { container } = render(<CompanyMark name="Cemig" tickers={[]} />)
    expect(container.querySelector('img')).toBeNull()
    expect(container).toHaveTextContent('C')
  })

  it('ticker fora do formato nunca vira caminho de arquivo', () => {
    const { container } = render(<CompanyMark name="X" tickers={['../../etc/passwd']} />)
    expect(container.querySelector('img')).toBeNull()
  })
})
