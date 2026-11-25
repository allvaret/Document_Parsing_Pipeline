import { useId, useState, type KeyboardEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { searchCompanies } from '../api/endpoints'
import { useAsync } from '../hooks/useAsync'
import { useDebounced } from '../hooks/useDebounced'
import { t, tf } from '../i18n/pt'

const MAX_RESULTS = 8
const DEBOUNCE_MS = 250

/**
 * Busca de empresas: padrão ARIA "combobox com listbox". Teclado: setas movem, Enter abre,
 * Esc fecha. O foco nunca sai do input (a opção ativa é anunciada por aria-activedescendant).
 * Navega por id da empresa, que vale também para empresa sem ticker.
 */
export function SearchBox({ variant = 'compact' }: { variant?: 'hero' | 'compact' }) {
  const uid = useId()
  const listId = `${uid}-list`
  const navigate = useNavigate()
  const [q, setQ] = useState('')
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(-1)
  const term = useDebounced(q.trim(), DEBOUNCE_MS)

  const { state } = useAsync(
    (signal) => (term ? searchCompanies(term, MAX_RESULTS, 0, signal) : Promise.resolve(null)),
    [term],
  )

  // Resultados só valem para o que está digitado agora (senão Enter abriria um resultado velho).
  const settled = q.trim() === term && term !== ''
  const items = settled && state.status === 'success' && state.data ? state.data.items : []
  const showPopup = open && q.trim() !== ''

  const go = (id: number) => {
    setQ('')
    setOpen(false)
    setActive(-1)
    navigate(`/empresas/${id}`)
  }

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault()
        setOpen(true)
        if (items.length) setActive((i) => (i + 1) % items.length)
        break
      case 'ArrowUp':
        e.preventDefault()
        if (items.length) setActive((i) => (i <= 0 ? items.length - 1 : i - 1))
        break
      case 'Enter': {
        const target = items[active] ?? (items.length ? items[0] : undefined)
        if (target) {
          e.preventDefault()
          go(target.id)
        }
        break
      }
      case 'Escape':
        if (open) setOpen(false)
        else setQ('')
        break
    }
  }

  const status = !showPopup
    ? ''
    : !settled || state.status === 'loading'
      ? t('search.searching')
      : state.status === 'error'
        ? t('search.error')
        : items.length === 0
          ? t('search.none')
          : items.length === 1 ? t('search.countOne') : tf('search.count', { n: items.length })

  const hero = variant === 'hero'
  return (
    <div className={`relative ${hero ? 'w-full max-w-2xl' : 'w-full max-w-xs'}`}>
      <input
        type="search"
        role="combobox"
        aria-label={t('search.label')}
        aria-expanded={showPopup && items.length > 0}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={active >= 0 && items[active] ? `${uid}-opt-${active}` : undefined}
        autoComplete="off"
        placeholder={t('nav.searchPlaceholder')}
        value={q}
        onChange={(e) => { setQ(e.target.value); setOpen(true); setActive(-1) }}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onKeyDown={onKeyDown}
        className={`w-full rounded-sm border border-rule bg-paper text-ink placeholder:text-ink-soft ${
          hero ? 'px-5 py-4 text-lg' : 'px-3 py-1.5 text-sm'
        }`}
      />
      <div role="status" aria-live="polite" className="sr-only">{status}</div>
      {showPopup && (
        <div className="absolute inset-x-0 top-full z-20 mt-1 overflow-hidden rounded-sm border border-rule bg-paper text-ink shadow-lg">
          {items.length > 0 ? (
            <ul id={listId} role="listbox" aria-label={t('search.label')}>
              {items.map((c, i) => (
                <li
                  key={c.id}
                  id={`${uid}-opt-${i}`}
                  role="option"
                  aria-selected={i === active}
                  // mousedown (não click): o blur do input fecharia o popup antes do click.
                  onMouseDown={(e) => { e.preventDefault(); go(c.id) }}
                  onMouseEnter={() => setActive(i)}
                  className={`cursor-pointer px-4 py-2 ${i === active ? 'bg-paper-deep' : ''}`}
                >
                  <span className="font-medium">{c.name}</span>
                  {c.tickers.length > 0 && <span className="ml-2 text-sm text-ink-soft">{c.tickers.join(' · ')}</span>}
                </li>
              ))}
            </ul>
          ) : (
            <p id={listId} className="px-4 py-3 text-sm text-ink-soft">{status}</p>
          )}
        </div>
      )}
    </div>
  )
}
