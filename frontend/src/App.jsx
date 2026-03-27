import { useState, useEffect, useRef } from 'react'
import SearchBar from './components/SearchBar'
import LoadingState from './components/LoadingState'
import InsightDashboard from './components/InsightDashboard'
import ResultTabs from './components/ResultTabs'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export default function App() {
  const [status, setStatus] = useState('idle') // idle, loading, done, error
  const [data, setData] = useState(null)
  const [progress, setProgress] = useState({ step: '', progress: 0 })
  const [error, setError] = useState(null)
  const [analysisStatus, setAnalysisStatus] = useState('idle') // idle, analyzing, done, error
  const [analysisConfig, setAnalysisConfig] = useState(null) // Analysis capabilities info
  const [detailedError, setDetailedError] = useState(null) // Enhanced error information
  const [urlsPerSource, setUrlsPerSource] = useState(4) // Number of URLs to analyze per source
  const pollIntervalRef = useRef(null)

  // Fetch analysis capabilities on component mount
  useEffect(() => {
    fetchAnalysisCapabilities()
  }, [])

  const fetchAnalysisCapabilities = async () => {
    try {
      const response = await fetch(`${API_URL}/api/config`)
      if (response.ok) {
        const config = await response.json()
        setAnalysisConfig(config.content_analysis)
      }
    } catch (err) {
      console.warn('Could not fetch analysis capabilities:', err)
    }
  }

  const clearPolling = () => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current)
      pollIntervalRef.current = null
    }
  }

  useEffect(() => {
    return () => clearPolling()
  }, [])

  const handleSearch = async (searchParams) => {
    const { topic, searchMode, sources } = searchParams

    setStatus('loading')
    setData(null)
    setError(null)
    setProgress({ step: 'Starting search...', progress: 0 })
    clearPolling()

    try {
      // Start the search
      const response = await fetch(`${API_URL}/api/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          topic,
          search_mode: searchMode,
          sources: sources
        }),
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to start search')
      }

      const { job_id } = await response.json()

      // Poll for status
      pollIntervalRef.current = setInterval(async () => {
        try {
          const statusRes = await fetch(`${API_URL}/api/status/${job_id}`)
          const statusData = await statusRes.json()

          if (statusData.status === 'progress') {
            setProgress({
              step: statusData.step || 'Processing...',
              progress: statusData.progress || 0,
            })
          } else if (statusData.status === 'done') {
            clearPolling()
            setData({
              topic: statusData.topic,
              insights: statusData.insights,
              results: statusData.results,
              total_results: statusData.total_results,
              search_mode: statusData.search_mode,
              sources_searched: statusData.sources_searched
            })
            setStatus('done')
          } else if (statusData.status === 'error') {
            clearPolling()
            setError(statusData.error || 'An error occurred')
            setStatus('error')
          }
        } catch (err) {
          console.error('Polling error:', err)
        }
      }, 1000)

    } catch (err) {
      setError(err.message)
      setStatus('error')
    }
  }

  const handleDeepAnalysis = async () => {
    if (!data || analysisStatus === 'analyzing') return

    setAnalysisStatus('analyzing')
    setDetailedError(null)
    setProgress({ step: 'Starting deep analysis...', progress: 0 })

    try {
      // Call the deep analysis endpoint
      const response = await fetch(`${API_URL}/api/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          topic: data.topic,
          results: data.results,
          urls_per_source: urlsPerSource
        }),
      })

      if (!response.ok) {
        const errorData = await response.json()

        // Handle detailed error responses
        if (response.status === 503 && errorData.detail) {
          // Service unavailable - Ollama issues
          setDetailedError({
            type: 'service_unavailable',
            title: 'Content Analysis Unavailable',
            message: errorData.detail.error || 'Analysis service is not available',
            reason: errorData.detail.reason,
            troubleshooting: errorData.detail.troubleshooting || [],
            technicalDetails: errorData.detail.ollama_config
          })
          setAnalysisStatus('error')
          return
        } else {
          // Generic error
          throw new Error(errorData.detail?.error || errorData.detail || 'Failed to start deep analysis')
        }
      }

      const analysisResponse = await response.json()
      const { job_id, urls_to_analyze, estimated_duration_minutes } = analysisResponse

      // Update progress with analysis info
      setProgress({
        step: `Starting analysis of ${urls_to_analyze} URLs...`,
        progress: 5,
        details: `Estimated duration: ${estimated_duration_minutes} minutes`
      })

      // Poll for analysis progress
      const analysisInterval = setInterval(async () => {
        try {
          const statusRes = await fetch(`${API_URL}/api/status/${job_id}`)
          const statusData = await statusRes.json()

          if (statusData.status === 'progress') {
            const progressData = {
              step: statusData.step || 'Analyzing content...',
              progress: statusData.progress || 0,
            }

            // Add details if available
            if (statusData.details) {
              progressData.details = statusData.details
            }

            setProgress(progressData)
          } else if (statusData.status === 'done') {
            clearInterval(analysisInterval)

            // Check if analysis actually succeeded
            if (statusData.content_analysis_enabled) {
              setData({
                ...data,
                results: statusData.results,
                content_analysis_enabled: true
              })
              setAnalysisStatus('done')
              setProgress({ step: 'Analysis complete!', progress: 100 })
            } else {
              // Analysis completed but failed
              setDetailedError({
                type: 'analysis_failed',
                title: 'Analysis Incomplete',
                message: statusData.analysis_error || 'Analysis completed but no insights were generated',
                reason: statusData.error_details?.error || 'Unknown error during processing',
                troubleshooting: statusData.error_details?.troubleshooting || [
                  'Try running the analysis again',
                  'Check if Ollama is running properly'
                ]
              })
              setAnalysisStatus('error')
            }
          } else if (statusData.status === 'error') {
            clearInterval(analysisInterval)

            setDetailedError({
              type: 'processing_error',
              title: 'Analysis Failed',
              message: statusData.error || 'An error occurred during analysis',
              troubleshooting: [
                'Try running the analysis again',
                'Check your internet connection',
                'Verify that Ollama is running'
              ]
            })
            setAnalysisStatus('error')
          }
        } catch (err) {
          console.error('Analysis polling error:', err)
        }
      }, 2000) // Poll every 2 seconds for analysis

    } catch (err) {
      setDetailedError({
        type: 'network_error',
        title: 'Connection Error',
        message: err.message,
        troubleshooting: [
          'Check your internet connection',
          'Verify the server is running',
          'Try refreshing the page'
        ]
      })
      setAnalysisStatus('error')
    }
  }

  return (
    <div className="app-container">
      <header className="app-header">
        <h1 className="app-title">TopicLens</h1>
        <p className="app-subtitle">
          Discover curated resources about any topic from across the internet
        </p>
      </header>

      <SearchBar 
        onSearch={handleSearch} 
        isLoading={status === 'loading'}
        apiUrl={API_URL}
      />

      {status === 'loading' && (
        <LoadingState step={progress.step} progress={progress.progress} />
      )}

      {status === 'error' && (
        <div className="error-container">
          <h3>Something went wrong</h3>
          <p>{error}</p>
          <button
            className="search-button"
            style={{ marginTop: '16px' }}
            onClick={() => {
              setStatus('idle')
              setError(null)
            }}
          >
            Try Again
          </button>
        </div>
      )}

      {status === 'done' && data && (
        <>
          <InsightDashboard
            insights={data.insights}
            topic={data.topic}
            total={data.total_results}
          />

          {/* Deep Analysis Section */}
          <div className="deep-analysis-section">
            {/* Analysis Status Indicator */}
            {analysisConfig && (
              <div className={`analysis-status ${analysisConfig.available ? 'available' : 'unavailable'}`}>
                <span className="status-indicator">
                  {analysisConfig.available ? '🟢' : '🔴'}
                </span>
                <span className="status-text">
                  AI Analysis: {analysisConfig.available ? 'Available' : 'Unavailable'}
                  {analysisConfig.ollama_info?.model && ` (${analysisConfig.ollama_info.model})`}
                </span>
              </div>
            )}

            {/* Analysis Error Display */}
            {detailedError && (
              <div className="detailed-error-container">
                <div className="error-header">
                  <span className="error-icon">⚠️</span>
                  <h3>{detailedError.title}</h3>
                </div>

                <div className="error-content">
                  <p className="error-message">{detailedError.message}</p>

                  {detailedError.reason && (
                    <div className="error-reason">
                      <strong>Reason:</strong> {detailedError.reason}
                    </div>
                  )}

                  {detailedError.troubleshooting?.length > 0 && (
                    <div className="troubleshooting-section">
                      <strong>How to fix:</strong>
                      <ul>
                        {detailedError.troubleshooting.map((tip, index) => (
                          <li key={index}>{tip}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {detailedError.technicalDetails && (
                    <details className="technical-details">
                      <summary>Technical Details</summary>
                      <div className="tech-info">
                        <p><strong>Ollama URL:</strong> {detailedError.technicalDetails.url}</p>
                        <p><strong>Target Model:</strong> {detailedError.technicalDetails.model}</p>
                        {detailedError.technicalDetails.models_available?.length > 0 && (
                          <p><strong>Available Models:</strong> {detailedError.technicalDetails.models_available.join(', ')}</p>
                        )}
                      </div>
                    </details>
                  )}
                </div>

                <div className="error-actions">
                  <button
                    className="retry-button"
                    onClick={() => {
                      setDetailedError(null)
                      setAnalysisStatus('idle')
                      fetchAnalysisCapabilities() // Refresh capabilities
                    }}
                  >
                    Refresh Status
                  </button>

                  {detailedError.type !== 'service_unavailable' && (
                    <button
                      className="retry-analysis-button"
                      onClick={() => {
                        setDetailedError(null)
                        handleDeepAnalysis()
                      }}
                    >
                      Retry Analysis
                    </button>
                  )}
                </div>
              </div>
            )}

            {/* Analysis Prompt - only show if analysis available and no errors */}
            {!data.content_analysis_enabled &&
             analysisStatus !== 'done' &&
             analysisStatus !== 'analyzing' &&
             !detailedError &&
             analysisConfig?.available && (
              <div className="analysis-prompt">
                <div className="analysis-info">
                  <span className="analysis-icon">🧠</span>
                  <div>
                    <h3>Want deeper insights?</h3>
                    <p>AI can visit each webpage, extract full content, and provide detailed analysis including relevance scores, quality ratings, and actionable insights.</p>
                  </div>
                </div>

                <div className="analysis-config">
                  <label className="config-label">
                    URLs per source:
                    <select
                      value={urlsPerSource}
                      onChange={(e) => setUrlsPerSource(parseInt(e.target.value))}
                      className="urls-selector"
                    >
                      <option value={2}>2 URLs (Fast - ~1 min)</option>
                      <option value={3}>3 URLs (Quick - ~2 min)</option>
                      <option value={4}>4 URLs (Balanced - ~3 min)</option>
                      <option value={5}>5 URLs (Thorough - ~4 min)</option>
                      <option value={8}>8 URLs (Comprehensive - ~6 min)</option>
                    </select>
                  </label>
                  <div className="config-info">
                    <small>📊 Analyzes top {urlsPerSource} URLs from each source (~{Math.max(1, Object.keys(data?.results || {}).length - 1) * urlsPerSource} total)</small>
                  </div>
                </div>

                <button
                  className="deep-analysis-button"
                  onClick={handleDeepAnalysis}
                  disabled={analysisStatus === 'analyzing'}
                >
                  Start Deep Analysis
                </button>
              </div>
            )}

            {/* Analysis Progress */}
            {analysisStatus === 'analyzing' && (
              <div className="analysis-progress">
                <LoadingState
                  step={progress.step}
                  progress={progress.progress}
                  details={progress.details}
                />
                <p className="analysis-note">⏱️ This usually takes 2-5 minutes depending on the number of URLs</p>
              </div>
            )}

            {/* Analysis Complete */}
            {data.content_analysis_enabled && (
              <div className="analysis-complete">
                <span className="analysis-complete-icon">✅</span>
                <span>Deep analysis complete! Results now include AI insights for each webpage.</span>
              </div>
            )}
          </div>

          <ResultTabs results={data.results} />
        </>
      )}

      {status === 'idle' && (
        <div className="empty-state">
          <div className="empty-icon">🔭</div>
          <p>Enter a topic above to start exploring</p>
          <p className="empty-hint">
            💡 Tip: Click the ⚙️ icon to choose search method and platforms
          </p>
        </div>
      )}
    </div>
  )
}
