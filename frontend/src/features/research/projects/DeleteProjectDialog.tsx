import { useEffect, useRef, useState } from 'react';
import { ProjectApiError } from './api';

interface Props {
  title: string;
  onConfirm: () => Promise<void>;
  onCancel: () => void;
}

export function DeleteProjectDialog({ title, onConfirm, onCancel }: Props) {
  const dialog = useRef<HTMLDialogElement>(null);
  const cancel = useRef<HTMLButtonElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const element = dialog.current;
    element?.showModal();
    cancel.current?.focus();
    return () => element?.close();
  }, []);

  function cancelDialog() {
    if (busy) return;
    // Close the native modal before restoring focus outside its inert subtree.
    dialog.current?.close();
    onCancel();
  }

  async function confirm() {
    if (busy) return;
    setBusy(true);
    setError('');
    try {
      await onConfirm();
    } catch (caught) {
      setError(
        caught instanceof ProjectApiError
          ? caught.message
          : 'No se pudo eliminar el proyecto. Intenta nuevamente.',
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <dialog
      ref={dialog}
      className="rp-dialog"
      aria-labelledby="delete-title"
      aria-describedby="delete-description"
      onCancel={(event) => {
        event.preventDefault();
        cancelDialog();
      }}
    >
      <h2 id="delete-title">¿Eliminar investigación?</h2>
      <p id="delete-description">
        Se eliminará «{title}» del repositorio local. Esta acción no se puede
        deshacer.
      </p>
      {error && (
        <p role="alert" className="rp-error">
          {error}
        </p>
      )}
      <div className="rp-actions">
        <button
          ref={cancel}
          className="rp-secondary"
          disabled={busy}
          onClick={cancelDialog}
        >
          Cancelar
        </button>
        <button
          className="rp-danger"
          disabled={busy}
          onClick={() => void confirm()}
        >
          {busy ? 'Eliminando…' : 'Eliminar definitivamente'}
        </button>
      </div>
    </dialog>
  );
}
