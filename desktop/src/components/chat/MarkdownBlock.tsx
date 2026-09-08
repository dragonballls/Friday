import { useMemo, useState } from 'react'
import { marked } from 'marked'
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

marked.setOptions({ breaks: true, gfm: true })

export function MarkdownBlock({ content }: { content: string }) {
  const [copied, setCopied] = useState(false)
  const html = useMemo(() => marked.parse(content) as string, [content])

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(content)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1200)
    } catch {
      setCopied(false)
    }
  }

  return (
    <div className="group relative markdown-body text-sm leading-relaxed tracking-wide" style={{ color: '#ccc' }}>
      <button
        type="button"
        onClick={copy}
        aria-label={copied ? 'Copied message' : 'Copy message'}
        title={copied ? 'Copied' : 'Copy message'}
        className="absolute right-0 top-0 rounded-lg px-2 py-1 text-[10px] opacity-0 transition-opacity group-hover:opacity-100 focus:opacity-100"
        style={{ color: copied ? '#4ade80' : '#777', border: '1px solid rgba(255,255,255,0.08)' }}
      >
        {copied ? 'Copied' : 'Copy'}
      </button>
      <div dangerouslySetInnerHTML={{ __html: html }} />
    </div>
  )
}
