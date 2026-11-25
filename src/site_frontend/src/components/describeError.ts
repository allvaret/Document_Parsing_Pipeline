import { ApiError, NetworkError } from '../api/client'
import { t } from '../i18n/pt'

/** Mensagem humana para o erro. 404 não passa por aqui: a página decide o que mostrar. */
export function describeError(error: unknown): string {
  if (error instanceof NetworkError) return t('state.errorNetwork')
  if (error instanceof ApiError && error.status < 500) return error.message
  return t('state.errorServer')
}
