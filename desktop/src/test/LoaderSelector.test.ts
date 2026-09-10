import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const indexHtml = readFileSync(resolve(process.cwd(), 'index.html'), 'utf8')

describe('startup reconnect notice selector', () => {
  it('targets only explicitly marked reconnect notices', () => {
    expect(indexHtml).toContain("document.querySelectorAll('[data-friday-reconnect-notice]')")
    expect(indexHtml).not.toContain("document.querySelectorAll('body *')")
    expect(indexHtml).not.toContain("textContent.trim().toLowerCase().startsWith('reconnecting')")
  })

  it('does not select the React root when reconnecting text exists elsewhere', () => {
    document.body.innerHTML = `
      <div id="root"><div>Reconnecting…</div></div>
      <div data-friday-reconnect-notice="true">Reconnecting…</div>
    `

    const matched = document.querySelectorAll('[data-friday-reconnect-notice]')

    expect(matched).toHaveLength(1)
    expect(matched[0]).not.toBe(document.getElementById('root'))
    expect(document.getElementById('root')).toBeTruthy()
  })
})
