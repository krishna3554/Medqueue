export function Toast({ toast }) {
  if (!toast) return null;
  return <div className="toast" role="status">✓ {toast}</div>;
}
