// @vitest-environment node
/// <reference types="node" />
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import openapiTS, { astToString } from 'openapi-typescript'
import { expect, it } from 'vitest'

// schema.d.ts é GERADO do openapi.json. Se alguém alterar o JSON (ou o gerador) e esquecer
// de rodar `npm run gen:api`, os tipos ficam velhos sem o compilador perceber.
it('schema.d.ts está em dia com openapi.json', async () => {
  const dir = resolve(process.cwd(), 'src/api')
  const spec = JSON.parse(readFileSync(resolve(dir, 'openapi.json'), 'utf8'))
  const gerado = astToString(await openapiTS(spec))
  const commitado = readFileSync(resolve(dir, 'schema.d.ts'), 'utf8')
  // A CLI põe um comentário de cabeçalho no arquivo; a API programática não.
  const norm = (s: string) =>
    s.replace(/\r\n/g, '\n').replace(/^\/\*\*[\s\S]*?\*\/\s*/, '').trim()
  expect(norm(commitado), 'rode `npm run gen:api`').toBe(norm(gerado))
})
