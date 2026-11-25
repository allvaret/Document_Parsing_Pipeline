import { useEffect, useId, useState, type FormEvent } from 'react'
import { calculate, listMethods } from '../api/endpoints'
import type { CeilingResult, FieldInfo, MethodInfo } from '../api/types'
import { ErrorState } from '../components/ErrorState'
import { Loading } from '../components/Loading'
import { useAsync } from '../hooks/useAsync'
import { t, tf } from '../i18n/pt'
import {
  buildPayload, formatBRL, marginOfSafety, parseDecimal, toInput, type FormErrors,
} from '../lib/calculadora'

const SUFFIX: Record<FieldInfo['unidade'], string> = { moeda: 'R$', percentual: '%', numero: '' }

function Field({
  field, value, error, onChange,
}: { field: FieldInfo; value: string; error?: string; onChange: (v: string) => void }) {
  const id = useId()
  const helpId = `${id}-ajuda`
  const placeholder = field.padrao != null
    ? toInput(field.unidade === 'percentual' ? field.padrao * 100 : field.padrao)
    : tf('calc.example', { value: toInput(field.exemplo ?? 0) })
  return (
    <div>
      <label htmlFor={id} className="block font-medium text-ink">
        {field.rotulo}{' '}
        {!field.obrigatorio && <span className="font-normal text-ink-soft">{t('calc.optional')}</span>}
      </label>
      <div className="mt-1 flex items-stretch">
        {field.unidade === 'moeda' && <span className="flex items-center border border-r-0 border-rule px-3 text-ink-soft">R$</span>}
        <input
          id={id}
          name={field.nome}
          inputMode="decimal"
          autoComplete="off"
          value={value}
          placeholder={placeholder}
          onChange={(e) => onChange(e.target.value)}
          aria-invalid={error ? true : undefined}
          aria-describedby={helpId}
          className="w-full min-w-0 border border-rule bg-paper px-3 py-2 text-ink"
        />
        {field.unidade === 'percentual' && <span className="flex items-center border border-l-0 border-rule px-3 text-ink-soft">{SUFFIX.percentual}</span>}
      </div>
      <p id={helpId} className={`mt-1 text-sm ${error ? 'text-danger' : 'text-ink-soft'}`}>
        {error ?? field.ajuda}
        {!error && field.padrao != null && ` ${tf('calc.defaultHint', { value: placeholder + (field.unidade === 'percentual' ? '%' : '') })}`}
      </p>
    </div>
  )
}

function Result({ result, method, price }: { result: CeilingResult; method: MethodInfo; price: number | null }) {
  const margin = price !== null ? marginOfSafety(result.preco_teto, price) : null
  const pct = margin !== null ? Math.abs(margin).toLocaleString('pt-BR', { maximumFractionDigits: 1 }) : ''
  return (
    <section aria-labelledby="calc-resultado" className="rounded-sm border border-rule bg-paper px-6 py-6" role="status">
      <h2 id="calc-resultado" className="text-sm uppercase tracking-wide text-ink-soft">
        {t('calc.resultTitle')} · {method.nome}
      </h2>
      <p className="mt-1 font-serif text-5xl text-ink">{formatBRL(result.preco_teto)}</p>
      {margin !== null && (
        <p className="mt-3 text-ink">
          {margin > 0.05 ? tf('calc.marginBelow', { pct }) : margin < -0.05 ? tf('calc.marginAbove', { pct }) : t('calc.marginEqual')}
        </p>
      )}
      <p className="mt-4 text-sm text-ink-soft">{t('calc.warning')}</p>
    </section>
  )
}

export function CalculatorPage() {
  useEffect(() => { document.title = `${t('calc.title')} · RQ` }, [])
  const { state, reload } = useAsync((signal) => listMethods(signal), [])
  const [selected, setSelected] = useState<string | null>(null)
  const [values, setValues] = useState<Record<string, string>>({})
  const [price, setPrice] = useState('')
  const [errors, setErrors] = useState<FormErrors>({})
  const [result, setResult] = useState<CeilingResult | null>(null)
  const [failure, setFailure] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)

  if (state.status === 'loading') return <Loading />
  if (state.status === 'error') return <ErrorState error={state.error} onRetry={reload} />

  const methods = state.data
  const method = methods.find((m) => m.metodo === selected) ?? methods[0]
  const groups: [string, MethodInfo[]][] = [
    [t('calc.stocks'), methods.filter((m) => m.aplicacao === 'acao')],
    [t('calc.fiis'), methods.filter((m) => m.aplicacao === 'fii')],
  ]

  function choose(m: MethodInfo) {
    setSelected(m.metodo)
    setValues({})
    setErrors({})
    setResult(null)
    setFailure(null)
  }

  async function submit(e: FormEvent) {
    e.preventDefault()
    const { premises, errors: found } = buildPayload(method.campos, values)
    const priceRaw = price.trim() ? parseDecimal(price) : null
    if (price.trim() && (priceRaw === null || priceRaw <= 0)) found.cotacao = 'Digite uma cotação positiva, como 12,34.'
    setErrors(found)
    setFailure(null)
    if (Object.keys(found).length > 0) { setResult(null); return }
    setBusy(true)
    try {
      setResult(await calculate(method.metodo, premises))
    } catch (err) {
      setResult(null)
      setFailure(err)
    } finally {
      setBusy(false)
    }
  }

  const priceNumber = price.trim() ? parseDecimal(price) : null

  return (
    <div className="mx-auto max-w-2xl space-y-8">
      <header>
        <h1 className="font-serif text-4xl text-ink">{t('calc.title')}</h1>
        <p className="mt-2 text-ink-soft">{t('calc.intro')}</p>
      </header>

      <fieldset>
        <legend className="mb-2 font-medium text-ink">{t('calc.methodLabel')}</legend>
        <div className="space-y-4">
          {groups.map(([title, list]) => list.length > 0 && (
            <div key={title} role="radiogroup" aria-label={title}>
              <p className="mb-1 text-sm text-ink-soft">{title}</p>
              <div className="grid gap-2 sm:grid-cols-2">
                {list.map((m) => (
                  <label
                    key={m.metodo}
                    className={`cursor-pointer rounded-sm border px-3 py-2 ${m.metodo === method.metodo ? 'border-ink bg-ink text-paper' : 'border-rule text-ink hover:border-ink'}`}
                  >
                    <input
                      type="radio" name="metodo" value={m.metodo} className="sr-only"
                      checked={m.metodo === method.metodo} onChange={() => choose(m)}
                    />
                    {m.nome}
                  </label>
                ))}
              </div>
            </div>
          ))}
        </div>
      </fieldset>

      <section aria-label={method.nome}>
        <p className="text-ink">{method.descricao}</p>
        <p className="mt-1 text-sm text-ink-soft">
          {t('calc.formula')}: <code className="font-mono">{method.formula}</code>
        </p>
      </section>

      <form onSubmit={submit} noValidate className="space-y-5">
        <h2 className="font-serif text-2xl text-ink">{t('calc.premises')}</h2>
        {method.campos.map((f) => (
          <Field
            key={`${method.metodo}-${f.nome}`}
            field={f}
            value={values[f.nome] ?? ''}
            error={errors[f.nome]}
            onChange={(v) => setValues((cur) => ({ ...cur, [f.nome]: v }))}
          />
        ))}
        <Field
          field={{
            nome: 'cotacao', rotulo: t('calc.priceLabel'), unidade: 'moeda', ajuda: t('calc.priceHelp'),
            obrigatorio: false, padrao: null, exemplo: 12.34,
          }}
          value={price}
          error={errors.cotacao}
          onChange={setPrice}
        />
        {Object.keys(errors).length > 0 && <p role="alert" className="text-danger">{t('calc.formErrors')}</p>}
        <button type="submit" className="btn" disabled={busy}>{t('calc.submit')}</button>
      </form>

      {failure !== null && <ErrorState error={failure} />}
      {result && <Result result={result} method={method} price={priceNumber && priceNumber > 0 ? priceNumber : null} />}
    </div>
  )
}
