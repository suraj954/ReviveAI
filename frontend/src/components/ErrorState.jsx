export default function ErrorState({ message, onRetry }) {
  return (
    <div className="state-block error">
      <h3>Couldn't load this data</h3>
      <p>{message || 'The ReviveAI backend did not respond as expected.'}</p>
      {onRetry ? (
        <button className="btn" onClick={onRetry} style={{ marginTop: 4 }}>
          Retry
        </button>
      ) : null}
    </div>
  )
}
