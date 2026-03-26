export default function LoadingState({ step, progress }) {
  return (
    <div className="loading-container">
      <div className="loading-spinner"></div>
      <p className="loading-step">{step || 'Starting search...'}</p>
      <div className="progress-bar">
        <div
          className="progress-fill"
          style={{ width: `${progress || 0}%` }}
        ></div>
      </div>
      <p style={{ marginTop: '12px', color: '#6b6b7b', fontSize: '0.9rem' }}>
        {progress}% complete
      </p>
    </div>
  )
}
