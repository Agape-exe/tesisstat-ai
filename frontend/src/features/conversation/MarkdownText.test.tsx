import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MarkdownText } from './MarkdownText';

describe('MarkdownText', () => {
  it('renders headers, dividers, bold, italics and lists', () => {
    const markdown = `
### ¿Qué análisis podemos realizar con tus datos?

Tienes un diseño de investigación muy enriquecedor.

---

1. Comparación antes/después (Análisis Intragrupo)
2. Comparación entre secciones

- Nota importante con **negrita** y *cursiva*
- Otro punto con \`código\`

> Una cita textual
`;

    const { container } = render(<MarkdownText content={markdown} />);

    // Check h3
    const h3 = screen.getByRole('heading', { level: 3 });
    expect(h3).toBeDefined();
    expect(h3.textContent).toContain('¿Qué análisis podemos realizar con tus datos?');

    // Check hr
    expect(container.querySelector('hr')).not.toBeNull();

    // Check ol and ul
    expect(container.querySelector('ol')).not.toBeNull();
    expect(container.querySelector('ul')).not.toBeNull();

    // Check strong and em
    const strong = container.querySelector('strong');
    expect(strong?.textContent).toBe('negrita');

    const em = container.querySelector('em');
    expect(em?.textContent).toBe('cursiva');

    const code = container.querySelector('code');
    expect(code?.textContent).toBe('código');

    // Check blockquote
    const bq = container.querySelector('blockquote');
    expect(bq?.textContent).toContain('Una cita textual');
  });

  it('renders nothing on empty content', () => {
    const { container } = render(<MarkdownText content="" />);
    expect(container.firstChild).toBeNull();
  });
});
