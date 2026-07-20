import { useMemo } from 'react'
import DOMPurify from 'dompurify'
import { cn } from '@/utils/cn'

// DOMPurify 后处理：保留原有的链接 target/rel 安全策略
// target=_blank 强制补 rel="noopener noreferrer"，非法 target 值直接移除
DOMPurify.addHook('afterSanitizeAttributes', (node) => {
  if (node.tagName !== 'A') {
    return
  }

  const target = node.getAttribute('target')
  if (target === '_blank') {
    node.setAttribute('rel', 'noopener noreferrer')
  } else if (target && target !== '_self') {
    node.removeAttribute('target')
  }
})

const sanitizeHtml = (html: string): string => {
  if (!html.trim()) {
    return html
  }

  // USE_PROFILES html 白名单 + DOMPurify 默认协议白名单（http/https/mailto/tel/相对路径）
  return DOMPurify.sanitize(html, { USE_PROFILES: { html: true } })
}

interface SafeHtmlProps {
  html: string
  className?: string
}

export function SafeHtml({ html, className }: SafeHtmlProps) {
  const sanitizedHtml = useMemo(() => sanitizeHtml(html), [html])

  return (
    <div
      className={cn(
        'break-words leading-6 [&_a]:text-blue-600 [&_a]:underline-offset-2 [&_a]:transition-colors [&_a]:hover:underline [&_a]:hover:text-blue-700 dark:[&_a]:text-blue-400 dark:[&_a]:hover:text-blue-300',
        className,
      )}
      dangerouslySetInnerHTML={{ __html: sanitizedHtml }}
    />
  )
}
