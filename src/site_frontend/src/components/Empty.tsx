import type { ReactNode } from 'react'
import { t } from '../i18n/pt'

export function Empty({ title = t('state.emptyTitle'), children }: { title?: string; children?: ReactNode }) {
  return (
    <div className="rounded-sm border border-dashed border-rule px-6 py-10 text-center">
      <p className="font-serif text-xl text-ink">{title}</p>
      {children && <div className="mt-2 text-ink-soft">{children}</div>}
    </div>
  )
}
