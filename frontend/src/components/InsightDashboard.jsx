export default function InsightDashboard({ insights, topic, total }) {
  if (!insights) return null

  return (
    <div className="insight-dashboard">
      <div className="insight-header">
        <h2>Deep Insights: <span>{topic}</span></h2>
        <span className="total-badge">{total} resources aggregated</span>
      </div>

      <p className="insight-summary">{insights.summary}</p>

      <div className="insight-grid">
        <div className="insight-box">
          <h3>Key Trends</h3>
          <ul>
            {insights.trends?.map((trend, i) => (
              <li key={i}>{trend}</li>
            ))}
          </ul>
        </div>
        <div className="insight-box">
          <h3>Action Plan</h3>
          <ol>
            {insights.action_plan?.map((step, i) => (
              <li key={i}>{step}</li>
            ))}
          </ol>
        </div>
      </div>
    </div>
  )
}
