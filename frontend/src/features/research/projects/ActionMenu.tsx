import { useEffect, useId, useRef, useState } from 'react';

/** A button menu with roving focus, outside dismissal and focus restoration. */
export function ActionMenu({
  label,
  actions,
  disabled = false,
}: {
  label: string;
  actions: { label: string; onSelect: () => void; danger?: boolean }[];
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const id = useId();
  useEffect(() => {
    if (!open) return;
    root.current
      ?.querySelector<HTMLButtonElement>('[role="menuitem"]')
      ?.focus();
    const dismiss = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener('pointerdown', dismiss);
    return () => document.removeEventListener('pointerdown', dismiss);
  }, [open]);
  return (
    <div
      className="rp-action-menu"
      ref={root}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false);
      }}
      onKeyDown={(event) => {
        if (event.key === 'Escape') {
          setOpen(false);
          trigger.current?.focus();
        }
        if (!open) return;
        const buttons = Array.from(
          root.current?.querySelectorAll<HTMLButtonElement>(
            '[role="menuitem"]',
          ) ?? [],
        );
        const index = buttons.indexOf(
          document.activeElement as HTMLButtonElement,
        );
        const next =
          event.key === 'ArrowDown'
            ? (index + 1) % buttons.length
            : event.key === 'ArrowUp'
              ? (index - 1 + buttons.length) % buttons.length
              : event.key === 'Home'
                ? 0
                : event.key === 'End'
                  ? buttons.length - 1
                  : -1;
        if (next >= 0) {
          event.preventDefault();
          buttons[next]?.focus();
        }
      }}
    >
      <button
        ref={trigger}
        type="button"
        className="rp-menu-trigger"
        aria-label={label}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? id : undefined}
        disabled={disabled}
        onClick={() => setOpen(!open)}
        onKeyDown={(event) => {
          if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
            event.preventDefault();
            setOpen(true);
          }
        }}
      >
        ⋯
      </button>
      {open && (
        <div id={id} role="menu" aria-label={label} className="rp-menu-popover">
          {actions.map((action) => (
            <button
              key={action.label}
              type="button"
              role="menuitem"
              className={action.danger ? 'rp-delete' : 'rp-secondary'}
              onClick={() => {
                setOpen(false);
                trigger.current?.focus();
                action.onSelect();
              }}
            >
              {action.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
