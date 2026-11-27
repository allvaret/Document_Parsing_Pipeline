// Aliases legíveis dos tipos GERADOS do OpenAPI (schema.d.ts). Não escreva tipos de
// resposta à mão: mudou o schemas.py, rode `python -m site_backend.dump_openapi` e
// `npm run gen:api`; o compilador aponta o que quebrou aqui.
import type { components } from './schema'

type S = components['schemas']

export type Company = S['CompanyOut']
export type CompanyPage = S['CompanyPage']
export type ReportItem = S['ReportItem']
export type ReportCard = S['ReportCard']
export type ReportDetail = S['ReportDetail']
export type Keypoint = S['KeypointOut']
export type Summary = S['SummaryOut']
export type HeuristicSummary = S['HeuristicSummary']
export type MethodInfo = S['MetodoInfo']
export type FieldInfo = S['CampoInfo']
export type CeilingResult = S['ResultadoCalculo']
