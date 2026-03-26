import { useState } from 'react'
import ResultCard from './ResultCard'

// Tab order matching the spec - ALL platforms visible
const TAB_ORDER = [
  'youtube',
  'linkedin',
  'blogs',
  'reddit',
  'events',
  'facebook',
  'instagram',
  'twitter',
  'quora',
  'github',
]

const TAB_CONFIG = {
  youtube: { label: 'YouTube', icon: '🎥' },
  github: { label: 'GitHub', icon: '🐙' },
  linkedin: { label: 'LinkedIn', icon: '👤' },
  twitter: { label: 'Twitter/X', icon: '🐦' },
  facebook: { label: 'Facebook', icon: '📘' },
  instagram: { label: 'Instagram', icon: '📸' },
  quora: { label: 'Quora', icon: '❓' },
  blogs: { label: 'Blogs', icon: '📝' },
  reddit: { label: 'Reddit', icon: '👥' },
  events: { label: 'Events', icon: '📅' },
}

export default function ResultTabs({ results }) {
  // Show ALL tabs in defined order, not just ones with results
  const allTabs = TAB_ORDER.filter(key => key in TAB_CONFIG)

  // Find first tab with results for default selection
  const firstWithResults = allTabs.find(key => results[key]?.length > 0)
  const [activeTab, setActiveTab] = useState(firstWithResults || 'youtube')

  const totalResults = Object.values(results).reduce((sum, arr) => sum + (arr?.length || 0), 0)

  if (totalResults === 0) {
    return (
      <div className="empty-state">
        <div className="empty-icon">🔍</div>
        <p>No results found. Try a different topic.</p>
      </div>
    )
  }

  const currentResults = results[activeTab] || []

  return (
    <div className="tabs-container">
      <div className="tabs-list">
        {allTabs.map(tabKey => {
          const config = TAB_CONFIG[tabKey]
          const count = results[tabKey]?.length || 0
          const hasResults = count > 0

          return (
            <button
              key={tabKey}
              className={`tab-button ${activeTab === tabKey ? 'active' : ''} ${!hasResults ? 'empty' : ''}`}
              onClick={() => setActiveTab(tabKey)}
            >
              {config.icon} {config.label}
              <span className={`tab-count ${!hasResults ? 'zero' : ''}`}>{count}</span>
            </button>
          )
        })}
      </div>

      <div className="results-grid">
        {currentResults.length > 0 ? (
          currentResults.map((item, index) => (
            <ResultCard key={`${activeTab}-${index}`} item={item} />
          ))
        ) : (
          <div className="no-results-tab">
            <p>No {TAB_CONFIG[activeTab]?.label} results found for this topic.</p>
          </div>
        )}
      </div>
    </div>
  )
}
