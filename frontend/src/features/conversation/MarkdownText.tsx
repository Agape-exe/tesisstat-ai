import React from 'react';

/**
 * Lightweight, safe Markdown renderer for chat messages.
 * Supports:
 * - **bold** and *italic*
 * - `code` snippets
 * - [links](url)
 * - Numbered lists (1. , 2. )
 * - Bulleted lists (- , * )
 * - Paragraph separation and line breaks
 */

function renderInline(text: string): React.ReactNode[] {
  // Regex to match **bold**, *italic*, `code`, and [text](url)
  const regex = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|\[[^\]]+\]\([^)]+\))/g;
  const parts = text.split(regex);

  return parts.map((part, index) => {
    if (!part) return null;
    if (part.startsWith('**') && part.endsWith('**')) {
      return (
        <strong key={index} style={{ fontWeight: 600 }}>
          {part.slice(2, -2)}
        </strong>
      );
    }
    if (part.startsWith('*') && part.endsWith('*')) {
      return (
        <em key={index} style={{ fontStyle: 'italic' }}>
          {part.slice(1, -1)}
        </em>
      );
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      return (
        <code
          key={index}
          style={{
            backgroundColor: 'rgba(0,0,0,0.06)',
            padding: '2px 5px',
            borderRadius: '4px',
            fontSize: '0.88em',
            fontFamily: 'monospace',
          }}
        >
          {part.slice(1, -1)}
        </code>
      );
    }
    const linkMatch = part.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
    if (linkMatch) {
      return (
        <a
          key={index}
          href={linkMatch[2]}
          target="_blank"
          rel="noreferrer"
          style={{ color: '#4f46e5', textDecoration: 'underline' }}
        >
          {linkMatch[1]}
        </a>
      );
    }
    return part;
  });
}

export function MarkdownText({
  content,
  isUser = false,
}: {
  content: string;
  isUser?: boolean;
}) {
  if (!content) return null;

  // Split into blocks by double newlines
  const blocks = content.split(/\n\s*\n/);

  return (
    <div
      className="agentic-markdown-body"
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '0.6rem',
        color: isUser ? '#ffffff' : '#1e293b',
      }}
    >
      {blocks.map((block, bIdx) => {
        const lines = block.split('\n').map((l) => l.trimEnd());

        // Check if block is a bulleted list
        const isBulletList = lines.every(
          (l) => l.startsWith('- ') || l.startsWith('* '),
        );
        if (isBulletList) {
          return (
            <ul
              key={bIdx}
              style={{
                margin: 0,
                paddingLeft: '1.25rem',
                display: 'flex',
                flexDirection: 'column',
                gap: '0.25rem',
              }}
            >
              {lines.map((line, lIdx) => (
                <li key={lIdx} style={{ lineHeight: 1.5 }}>
                  {renderInline(line.replace(/^[-*]\s+/, ''))}
                </li>
              ))}
            </ul>
          );
        }

        // Check if block is a numbered list
        const isNumberedList = lines.every((l) => /^\d+\.\s+/.test(l));
        if (isNumberedList) {
          return (
            <ol
              key={bIdx}
              style={{
                margin: 0,
                paddingLeft: '1.25rem',
                display: 'flex',
                flexDirection: 'column',
                gap: '0.25rem',
              }}
            >
              {lines.map((line, lIdx) => (
                <li key={lIdx} style={{ lineHeight: 1.5 }}>
                  {renderInline(line.replace(/^\d+\.\s+/, ''))}
                </li>
              ))}
            </ol>
          );
        }

        // Normal paragraph with inline newlines as <br />
        return (
          <p key={bIdx} style={{ margin: 0, lineHeight: 1.55 }}>
            {lines.map((line, lIdx) => (
              <React.Fragment key={lIdx}>
                {lIdx > 0 && <br />}
                {renderInline(line)}
              </React.Fragment>
            ))}
          </p>
        );
      })}
    </div>
  );
}
