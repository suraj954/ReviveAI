export default function LoadingState({ label = 'Loading data from ReviveAI backend…' }) {
  return (
    <div className="state-block">
      <div className="spinner" role="status" aria-label="Loading" />
      <p>{label}</p>
    </div>
  )
}
