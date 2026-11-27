import { get, post } from './client'
import type {
  Company, CompanyPage, MethodInfo, ReportCard, ReportDetail, ReportItem, CeilingResult,
} from './types'

// O site navega por id (acha também empresa sem ticker). Só GET.

export const MAX_PAGE = 50 // teto de `limit` em /empresas

export const searchCompanies = (q: string, limit = 20, offset = 0, signal?: AbortSignal) =>
  get<CompanyPage>('/empresas', { q, limit, offset }, signal)

/** Todas as empresas: pagina até `total` (a API limita a página a 50). */
export async function listAllCompanies(signal?: AbortSignal): Promise<Company[]> {
  const all: Company[] = []
  for (;;) {
    const page = await get<CompanyPage>('/empresas', { limit: MAX_PAGE, offset: all.length }, signal)
    all.push(...page.items)
    if (page.items.length === 0 || all.length >= page.total) return all
  }
}

export const getCompany = (id: number | string, signal?: AbortSignal) =>
  get<Company>(`/empresas/id/${encodeURIComponent(String(id))}`, undefined, signal)

export const listCompanyReports = (id: number | string, signal?: AbortSignal) =>
  get<ReportItem[]>(`/empresas/id/${encodeURIComponent(String(id))}/relatorios`, undefined, signal)

export const latestReports = (limit = 8, signal?: AbortSignal) =>
  get<ReportCard[]>('/relatorios', { limit }, signal)

export const getReport = (id: number | string, signal?: AbortSignal) =>
  get<ReportDetail>(`/relatorios/${encodeURIComponent(String(id))}`, undefined, signal)

// Calculadora: o formulário é gerado do catálogo da API; o cálculo é uma conta sem estado.
export const listMethods = (signal?: AbortSignal) => get<MethodInfo[]>('/calcular/metodos', undefined, signal)

export const calculate = (method: string, premises: Record<string, number>, signal?: AbortSignal) =>
  post<CeilingResult>(`/calcular/${encodeURIComponent(method)}`, premises, signal)
