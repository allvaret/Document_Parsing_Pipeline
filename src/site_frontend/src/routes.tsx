import { createBrowserRouter, type RouteObject } from 'react-router-dom'
import { Layout } from './layout/Layout'
import { HomePage } from './pages/HomePage'
import { NotFoundPage } from './pages/NotFoundPage'
import { CompanyPage } from './pages/CompanyPage'
import { ReportPage } from './pages/ReportPage'
import { CalculatorPage } from './pages/CalculatorPage'

// Exportadas à parte para os testes montarem com `createMemoryRouter`.
export const routes: RouteObject[] = [
  {
    element: <Layout />,
    children: [
      { path: '/', element: <HomePage /> },
      { path: '/empresas/:id', element: <CompanyPage /> },
      { path: '/relatorios/:id', element: <ReportPage /> },
      { path: '/calculadora', element: <CalculatorPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]

export const createRouter = () => createBrowserRouter(routes)
