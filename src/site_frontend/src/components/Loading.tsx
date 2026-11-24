import { t } from '../i18n/pt'

export function Loading({ label = t('state.loading') }: { label?: string }) {
  return (
    <div role="status" aria-live="polite" className="flex items-center gap-3 py-12 text-ink-soft">
      <span aria-hidden className="size-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
      <span>{label}</span>
    </div>
  )
}
