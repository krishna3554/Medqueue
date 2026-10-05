export function AuditLog({ audit, auditError }) {
  return (
    <section className="detail-section">
      <h3>Audit log (admin only)</h3>
      {auditError ? <p className="explain">{auditError}</p> : audit.length ? audit.map((event) => <p className="explain" key={event.id}>#{event.id} {event.action} by {event.actor}</p>) : <p className="explain">No audit events.</p>}
    </section>
  );
}
