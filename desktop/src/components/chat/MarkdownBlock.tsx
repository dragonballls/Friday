import { useMemo } from 'react'
import { marked, type RendererObject } from 'marked'
import { markedHighlight } from 'marked-highlight'
import 'highlight.js/styles/atom-one-dark.css'
import hljs from 'highlight.js/lib/core'
import typescript from 'highlight.js/lib/languages/typescript'
import python from 'highlight.js/lib/languages/python'
import javascript from 'highlight.js/lib/languages/javascript'
import bash from 'highlight.js/lib/languages/bash'
import json from 'highlight.js/lib/languages/json'
import css from 'highlight.js/lib/languages/css'
import xml from 'highlight.js/lib/languages/xml'

hljs.registerLanguage('typescript', typescript)
hljs.registerLanguage('python', python)
hljs.registerLanguage('javascript', javascript)
hljs.registerLanguage('bash', bash)
hljs.registerLanguage('json', json)
hljs.registerLanguage('css', css)
hljs.registerLanguage('xml', xml)
hljs.registerLanguage('html', xml)

marked.use(markedHighlight({
  langPrefix: 'hljs language-',
  highlight(code: string, lang: string) {
    if (lang && hljs.getLanguage(lang)) {
      return hljs.highlight(code, { language: lang }).value
    }
    return hljs.highlightAuto(code).value
  },
}))

// Assistant output is rendered into the DOM, so raw HTML from a response must
// remain text rather than becoming executable markup. Markdown formatting and
// fenced code blocks continue to work normally.
const escapeHtml = (value: string) => value
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;')
  .replace(/'/g, '&#39;')

const safeMarkdownRenderer: RendererObject = {
  html({ raw }: { raw: string }) {
    return escapeHtml(raw)
  },
}

marked.use({ renderer: safeMarkdownRenderer })
marked.setOptions({ breaks: true, gfm: true })

export function MarkdownBlock({ content }: { content: string }) {
  const html = useMemo(() => marked.parse(content) as string, [content])
  return <div className="markdown-body text-sm leading-relaxed tracking-wide" style={{ color: '#ccc' }} dangerouslySetInnerHTML={{ __html: html }} />
}
