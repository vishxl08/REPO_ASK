export interface ToastMessage {
  id: number;
  text: string;
  variant: "success" | "error";
}

interface Props {
  toasts: ToastMessage[];
  onDismiss: (id: number) => void;
}

export default function Toast({ toasts, onDismiss }: Props) {
  if (toasts.length === 0) return null;

  return (
    <div className="toast-stack">
      {toasts.map((toast) => (
        <div key={toast.id} className={`toast toast--${toast.variant}`} onClick={() => onDismiss(toast.id)}>
          <span aria-hidden="true">{toast.variant === "success" ? "✓" : "✕"}</span>
          <span>{toast.text}</span>
        </div>
      ))}
    </div>
  );
}
