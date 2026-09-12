import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const indexHtml = readFileSync(resolve(process.cwd(), 'index.html'), 'utf8')

describe('Jarvis root document', () => {
  it('declares Jarvis branding and a single application root', () => {
    expect(indexHtml).toContain('<meta name="application-name" content="Jarvis" />')
    expect(indexHtml).toContain('<title>Jarvis</title>')
    expect(indexHtml).toContain('<div id="root"></div>')
    expect(indexHtml).toContain('<script type="module" src="/src/main.tsx"></script>')
  })
})
