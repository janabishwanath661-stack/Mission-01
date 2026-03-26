export default function ResultCard({ item }) {
  const {
    title, url, description, thumbnail, source,
    // GitHub
    stars, language, forks,
    // YouTube
    channel, subscribers,
    // Reddit
    score,
    // Twitter
    username, content_type,
    // Blog
    platform, author, reading_time, reactions, domain
  } = item

  return (
    <div className="result-card">
      <a href={url} target="_blank" rel="noopener noreferrer">
        {thumbnail && (
          <img
            src={thumbnail}
            alt={title}
            className="result-thumbnail"
            onError={(e) => {
              e.target.style.display = 'none'
            }}
          />
        )}
        <h3 className="result-title">{title}</h3>
        <p className="result-description">{description}</p>
        <div className="result-meta">
          <span className="result-source">{platform || source}</span>
          <div className="result-stats">
            {/* GitHub stats */}
            {stars !== undefined && <span>⭐ {stars.toLocaleString()}</span>}
            {language && <span>{language}</span>}
            {forks !== undefined && forks > 0 && <span>🍴 {forks.toLocaleString()}</span>}
            {/* YouTube stats */}
            {channel && <span>📺 {channel}</span>}
            {subscribers !== undefined && <span>👥 {subscribers.toLocaleString()}</span>}
            {/* Reddit stats */}
            {score !== undefined && <span>⬆️ {score}</span>}
            {/* Twitter stats */}
            {username && <span>{username}</span>}
            {content_type && content_type !== 'tweet' && <span>📌 {content_type}</span>}
            {/* Blog stats */}
            {author && <span>✍️ {author}</span>}
            {reading_time !== undefined && reading_time > 0 && <span>📖 {reading_time} min</span>}
            {reactions !== undefined && reactions > 0 && <span>❤️ {reactions}</span>}
            {domain && !platform && <span>🌐 {domain}</span>}
          </div>
        </div>
      </a>
    </div>
  )
}
