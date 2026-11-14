import React from 'react';

/**
 * Lightweight, robust Markdown renderer for chat messages.
 * Handles:
 * - Headers (# H1, ## H2, ### H3, #### H4)
 * - Horizontal rules (---, ***, ___)
 * - Unordered lists (- , * )
 * - Ordered lists (1. , 2. )
 * - Multi-line list items and continuations
 * - Blockquotes (> )
 * - Inline formatting: **bold**, *italic*, ***bold italic***, `code`, and [links](url)
 */

function renderInline(text: unknown, isUser = false): React.ReactNode[] {
  if (!text) return [];
  if (typeof text !== 'string') return [String(text)];

  // Match $$math$$, $math$, ***bold italic***, **bold**, *italic*, `code`, [text](url)
  const regex = /(\$\$[^$]+\$\$|\$[^$\n]+\$|\*\*\*[^*]+\*\*\*|\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|\[[^\]]+\]\([^)]+\))/g;
  const parts = text.split(regex);

  return parts.map((part, index) => {
    if (!part) return null;

    // Display LaTeX math $$...$$
    if (part.startsWith('$$') && part.endsWith('$$') && part.length > 4) {
      const inner = part.slice(2, -2).trim();
      return (
        <span
          key={index}
          style={{
            display: 'inline-block',
            fontStyle: 'italic',
            fontFamily: 'Cambria, "Times New Roman", serif',
            fontWeight: 500,
            padding: '0 4px',
          }}
        >
          {inner}
        </span>
      );
    }

    // Inline LaTeX math $...$ (e.g. $N = 23$, $p < 0.05$)
    if (part.startsWith('$') && part.endsWith('$') && part.length > 2) {
      const inner = part.slice(1, -1).trim();
      return (
        <span
          key={index}
          style={{
            fontStyle: 'italic',
            fontFamily: 'Cambria, "Times New Roman", serif',
            fontWeight: 500,
            padding: '0 2px',
          }}
        >
          {inner}
        </span>
      );
    }

    // Bold + Italic
    if (part.startsWith('***') && part.endsWith('***') && part.length > 6) {
      return (
        <strong key={index} style={{ fontWeight: 650 }}>
          <em style={{ fontStyle: 'italic' }}>{part.slice(3, -3)}</em>
        </strong>
      );
    }

    // Bold
    if (part.startsWith('**') && part.endsWith('**') && part.length > 4) {
      return (
        <strong key={index} style={{ fontWeight: 650 }}>
          {part.slice(2, -2)}
        </strong>
      );
    }

    // Italic
    if (part.startsWith('*') && part.endsWith('*') && part.length > 2) {
      return (
        <em key={index} style={{ fontStyle: 'italic' }}>
          {part.slice(1, -1)}
        </em>
      );
    }

    // Inline code
    if (part.startsWith('`') && part.endsWith('`') && part.length > 2) {
      return (
        <code
          key={index}
          style={{
            backgroundColor: isUser ? 'rgba(255,255,255,0.2)' : 'rgba(0,0,0,0.06)',
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

    // Link
    const linkMatch = part.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
    if (linkMatch) {
      return (
        <a
          key={index}
          href={linkMatch[2]}
          target="_blank"
          rel="noreferrer"
          style={{
            color: isUser ? '#ffffff' : '#4f46e5',
            textDecoration: 'underline',
            fontWeight: 500,
          }}
        >
          {linkMatch[1]}
        </a>
      );
    }

    return part;
  });
}

type ParsedBlock =
  | { type: 'header'; level: number; text: string }
  | { type: 'hr' }
  | { type: 'blockquote'; lines: string[] }
  | { type: 'ul'; items: string[] }
  | { type: 'ol'; items: { num: string; text: string }[] }
  | { type: 'p'; lines: string[] };

function parseMarkdownBlocks(content: string): ParsedBlock[] {
  const lines = content.replace(/\r\n/g, '\n').split('\n');
  const blocks: ParsedBlock[] = [];
  let currentBlock: ParsedBlock | null = null;

  const flush = () => {
    if (currentBlock) {
      blocks.push(currentBlock);
      currentBlock = null;
    }
  };

  for (let i = 0; i < lines.length; i++) {
    const rawLine = lines[i];
    const trimmed = rawLine.trim();

    // 1. Blank line -> flush current block
    if (!trimmed) {
      flush();
      continue;
    }

    // 2. Horizontal divider: ---, ***, ___
    if (/^(?:---|[*]{3}|___)$/.test(trimmed)) {
      flush();
      blocks.push({ type: 'hr' });
      continue;
    }

    // 3. Headers: #, ##, ###, ####
    const headerMatch = trimmed.match(/^(#{1,4})\s+(.+)$/);
    if (headerMatch) {
      flush();
      blocks.push({
        type: 'header',
        level: headerMatch[1].length,
        text: headerMatch[2],
      });
      continue;
    }

    // 4. Blockquote: > text
    const quoteMatch = trimmed.match(/^>\s*(.+)$/);
    if (quoteMatch) {
      if (currentBlock && currentBlock.type === 'blockquote') {
        currentBlock.lines.push(quoteMatch[1]);
      } else {
        flush();
        currentBlock = { type: 'blockquote', lines: [quoteMatch[1]] };
      }
      continue;
    }

    // 5. Ordered list item: 1. text
    const olMatch = trimmed.match(/^(\d+)\.\s+(.+)$/);
    if (olMatch) {
      if (currentBlock && currentBlock.type === 'ol') {
        currentBlock.items.push({ num: olMatch[1], text: olMatch[2] });
      } else {
        flush();
        currentBlock = {
          type: 'ol',
          items: [{ num: olMatch[1], text: olMatch[2] }],
        };
      }
      continue;
    }

    // 6. Unordered list item: - text or * text
    const ulMatch = trimmed.match(/^[-*]\s+(.+)$/);
    if (ulMatch) {
      if (currentBlock && currentBlock.type === 'ul') {
        currentBlock.items.push(ulMatch[1]);
      } else {
        flush();
        currentBlock = {
          type: 'ul',
          items: [ulMatch[1]],
        };
      }
      continue;
    }

    // 7. Continuation or regular paragraph line
    if (currentBlock) {
      if (currentBlock.type === 'p') {
        currentBlock.lines.push(trimmed);
      } else if (currentBlock.type === 'ol' && currentBlock.items.length > 0) {
        // Multi-line ordered list item description
        const last = currentBlock.items[currentBlock.items.length - 1];
        last.text += ' ' + trimmed;
      } else if (currentBlock.type === 'ul' && currentBlock.items.length > 0) {
        // Multi-line bullet item description
        currentBlock.items[currentBlock.items.length - 1] += ' ' + trimmed;
      } else {
        flush();
        currentBlock = { type: 'p', lines: [trimmed] };
      }
    } else {
      currentBlock = { type: 'p', lines: [trimmed] };
    }
  }

  flush();
  return blocks;
}

export function MarkdownText({
  content,
  isUser = false,
}: {
  content: string;
  isUser?: boolean;
}) {
  if (!content) return null;

  const blocks = parseMarkdownBlocks(content);

  return (
    <div
      className="agentic-markdown-body"
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '0.65rem',
        color: isUser ? '#ffffff' : '#1e293b',
        lineHeight: 1.55,
      }}
    >
      {blocks.map((block, bIdx) => {
        if (block.type === 'hr') {
          return (
            <hr
              key={bIdx}
              style={{
                border: 'none',
                borderTop: isUser ? '1px solid rgba(255,255,255,0.3)' : '1px solid #cbd5e1',
                margin: '0.5rem 0',
                width: '100%',
              }}
            />
          );
        }

        if (block.type === 'header') {
          const fontSizes: Record<number, string> = {
            1: '1.25rem',
            2: '1.12rem',
            3: '1.02rem',
            4: '0.95rem',
          };

          const style: React.CSSProperties = {
            margin: '0.4rem 0 0.2rem 0',
            fontSize: fontSizes[block.level] || '1rem',
            fontWeight: 650,
            color: isUser ? '#ffffff' : '#0f172a',
            lineHeight: 1.3,
          };

          if (block.level === 1) {
            return (
              <h1 key={bIdx} style={style}>
                {renderInline(block.text, isUser)}
              </h1>
            );
          }
          if (block.level === 2) {
            return (
              <h2 key={bIdx} style={style}>
                {renderInline(block.text, isUser)}
              </h2>
            );
          }
          if (block.level === 3) {
            return (
              <h3 key={bIdx} style={style}>
                {renderInline(block.text, isUser)}
              </h3>
            );
          }
          return (
            <h4 key={bIdx} style={style}>
              {renderInline(block.text, isUser)}
            </h4>
          );
        }

        if (block.type === 'blockquote') {
          return (
            <blockquote
              key={bIdx}
              style={{
                margin: '0.25rem 0',
                paddingLeft: '0.85rem',
                borderLeft: `3px solid ${isUser ? 'rgba(255,255,255,0.5)' : '#6366f1'}`,
                color: isUser ? 'rgba(255,255,255,0.9)' : '#475569',
                fontStyle: 'italic',
              }}
            >
              {block.lines.map((line, lIdx) => (
                <div key={lIdx}>{renderInline(line, isUser)}</div>
              ))}
            </blockquote>
          );
        }

        if (block.type === 'ul') {
          return (
            <ul
              key={bIdx}
              style={{
                margin: '0.2rem 0',
                paddingLeft: '1.35rem',
                display: 'flex',
                flexDirection: 'column',
                gap: '0.35rem',
              }}
            >
              {block.items.map((item, iIdx) => (
                <li key={iIdx} style={{ lineHeight: 1.5 }}>
                  {renderInline(item, isUser)}
                </li>
              ))}
            </ul>
          );
        }

        if (block.type === 'ol') {
          return (
            <ol
              key={bIdx}
              style={{
                margin: '0.2rem 0',
                paddingLeft: '1.35rem',
                display: 'flex',
                flexDirection: 'column',
                gap: '0.35rem',
              }}
            >
              {block.items.map((item, iIdx) => (
                <li key={iIdx} style={{ lineHeight: 1.5 }}>
                  {renderInline(item.text, isUser)}
                </li>
              ))}
            </ol>
          );
        }

        // Paragraph
        return (
          <p key={bIdx} style={{ margin: 0, lineHeight: 1.55 }}>
            {block.lines.map((line, lIdx) => (
              <React.Fragment key={lIdx}>
                {lIdx > 0 && <br />}
                {renderInline(line, isUser)}
              </React.Fragment>
            ))}
          </p>
        );
      })}
    </div>
  );
}
