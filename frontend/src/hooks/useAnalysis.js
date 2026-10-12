import { useState, useCallback } from 'react';
import api from '../api/client';

export function useAnalysis() {
  const [status, setStatus] = useState('idle');
  const [result, setResult] = useState(null);
  const [progress, setProgress] = useState({ stage: '', message: '', pct: 0 });

  const startAnalysis = useCallback(async (ticker) => {
    setStatus('loading');
    setResult(null);
    setProgress({ stage: 'validating', message: 'Fetching data...', pct: 10 });

    try {
      const response = await api.post('/analyze', { ticker });
      const data = response.data;

      if (data.status === 'complete' && data.result) {
        setResult(data);
        setStatus('complete');
        setProgress({ stage: 'complete', message: 'Analysis complete', pct: 100 });
      } else {
        setProgress({ stage: 'fetching_data', message: 'Processing...', pct: 50 });
        // Poll for the result if not returned immediately
        setTimeout(() => {
          setResult(data);
          setStatus('complete');
          setProgress({ stage: 'complete', message: 'Analysis complete', pct: 100 });
        }, 500);
      }
    } catch (err) {
      setStatus('error');
      const msg = err?.detail || err?.message || 'Analysis failed. Is the backend running?';
      setProgress({ stage: 'error', message: msg, pct: 0 });
    }
  }, []);

  const reset = useCallback(() => {
    setStatus('idle');
    setResult(null);
    setProgress({ stage: '', message: '', pct: 0 });
  }, []);

  return { startAnalysis, reset, status, result, progress };
}
