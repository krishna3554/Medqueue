export function OverrideModal({ level, setLevel, reason, setReason, onSubmit, onClose }) {
  return (
    <div className="modal-backdrop">
      <form className="modal" onSubmit={onSubmit}>
        <button type="button" className="modal-close" onClick={onClose}>×</button>
        <p className="modal-kicker">Clinical override</p>
        <h2>Set a new priority</h2>
        <label>Urgency level<select value={level} onChange={(e) => setLevel(e.target.value)}>{[1, 2, 3, 4, 5].map((x) => <option key={x} value={x}>Level {x}</option>)}</select></label>
        <label>Override reason<textarea required minLength="3" value={reason} onChange={(e) => setReason(e.target.value)} /></label>
        <div className="modal-actions"><button type="button" onClick={onClose}>Cancel</button><button className="primary-button">Save override</button></div>
      </form>
    </div>
  );
}
