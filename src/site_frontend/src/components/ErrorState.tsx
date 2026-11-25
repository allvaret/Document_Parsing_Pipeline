import { t } from '../i18n/pt'
import { describeError } from './describeError'

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <div role="alert" className="rounded-sm border border-danger/40 bg-danger/5 px-6 py-8">
      <p className="font-serif text-xl text-ink">{t('state.errorTitle')}</p>
      <p className="mt-1 text-ink-soft">{describeError(error)}</p>
      {onRetry && (
        <button type="button" onClick={onRetry} className="btn mt-4">
          {t('state.retry')}
        </button>
      )}
    </div>
  )
}
