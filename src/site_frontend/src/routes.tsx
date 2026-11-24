import { createBrowserRouter, type RouteObject } from 'react-router-dom'
import { Layout } from './layout/Layout'
import { NotFoundPage } from './pages/NotFoundPage'
import { CompanyPage } from './pages/CompanyPage'
import { Placeholder } from './pages/Placeholder'
import { ReportPage } from './pages/ReportPage'

// Exportadas à parte para os testes montarem com `createMemoryRouter`.
export const routes: RouteObject[] = [
  {
    element: <Layout />,
    children: [
      { path: '/', element: <Placeholder name="Home" /> },
      { path: '/empresas/:id', element: <CompanyPage /> },
      { path: '/relatorios/:id', element: <ReportPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]

export const createRouter = () => createBrowserRouter(routes)
