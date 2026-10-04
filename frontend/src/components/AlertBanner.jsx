export function AlertBanner({ count, live, soundOn, onToggleSound, latestIds }) {
  if (!count) return null;
  return (
    <section className="alert" role="alert">
      <div className="alert-icon">!</div>
      <div>
        <strong>{count} red-flag patient{count === 1 ? '' : 's'} need immediate review</strong>
        <p>{live ? 'Live update via WebSocket.' : 'Live updates unavailable — polling every 5 seconds.'}{latestIds && latestIds.length ? ` Latest: #${latestIds.join(', #')}.` : ''}</p>
      </div>
      <button type="button" onClick={onToggleSound}>{soundOn ? 'Mute alert' : 'Sound on'}</button>
    </section>
  );
}
