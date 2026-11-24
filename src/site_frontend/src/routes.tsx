import { createBrowserRouter, type RouteObject } from 'react-router-dom'
import { Layout } from './layout/Layout'
import { NotFoundPage } from './pages/NotFoundPage'
import { Placeholder } from './pages/Placeholder'

// Exportadas à parte para os testes montarem com `createMemoryRouter`.
export const routes: RouteObject[] = [
  {
    element: <Layout />,
    children: [
      { path: '/', element: <Placeholder name="Home" /> },
      { path: '/empresas/:id', element: <Placeholder name="Empresa" /> },
      { path: '/relatorios/:id', element: <Placeholder name="Relatório" /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]

export const createRouter = () => createBrowserRouter(routes)
