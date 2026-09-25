import React, { useEffect, useRef, useState } from 'react';

/**
 * Standardized dropdown trigger + menu. Handles outside-click and Escape to
 * close, and keeps the menu within the viewport (see .dropdown-menu in
 * styles.css) so it never clips or overflows the shell.
 *
 *   <Dropdown
 *     trigger={<button className="btn btn-secondary btn-sm">Actions ▾</button>}
 *     items={[
 *       { label: 'Approve block', onClick: handleApprove },
 *       { label: 'Reject block', onClick: handleReject, danger: true },
 *     ]}
 *   />
 */
export default function Dropdown({ trigger, items = [], align = 'right', onOpenChange }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    function handleClick(e) {
      if (ref.current && !ref.current.contains(e.target)) {
        setOpen(false);
      }
    }
    function handleKey(e) {
      if (e.key === 'Escape') setOpen(false);
    }
    document.addEventListener('mousedown', handleClick);
    document.addEventListener('keydown', handleKey);
    return () => {
      document.removeEventListener('mousedown', handleClick);
      document.removeEventListener('keydown', handleKey);
    };
  }, []);

  useEffect(() => {
    if (onOpenChange) onOpenChange(open);
  }, [open]);

  return (
    <div className="dropdown" ref={ref}>
      <span className="dropdown-trigger" onClick={() => setOpen((v) => !v)}>
        {trigger}
      </span>

      {open && (
        <div className={`dropdown-menu${align === 'left' ? ' align-left' : ''}`} role="menu">
          {items.map((item, i) =>
            item.divider ? (
              <div className="dropdown-divider" key={`div-${i}`} />
            ) : (
              <button
                key={item.key || item.label || i}
                type="button"
                role="menuitem"
                className={`dropdown-item${item.danger ? ' danger' : ''}${item.selected ? ' selected' : ''}`}
                onClick={() => {
                  setOpen(false);
                  item.onClick && item.onClick();
                }}
                disabled={item.disabled}
              >
                {item.icon && <span>{item.icon}</span>}
                <span>{item.label}</span>
              </button>
            )
          )}
        </div>
      )}
    </div>
  );
}
