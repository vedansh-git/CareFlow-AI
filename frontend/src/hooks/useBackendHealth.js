import { useState, useEffect, useCallback } from 'react';
import { checkHealth } from '../services/api';

export const useBackendHealth = () => {
  const [status, setStatus] = useState('checking'); // 'checking' | 'connected' | 'error'
  const [healthData, setHealthData] = useState(null);
  const [errorDetails, setErrorDetails] = useState(null);

  const fetchHealth = useCallback(async () => {
    setStatus('checking');
    const result = await checkHealth();
    if (result.success) {
      setHealthData(result.data);
      setStatus('connected');
      setErrorDetails(null);
    } else {
      setHealthData(null);
      setStatus('error');
      setErrorDetails(result.error);
    }
  }, []);

  useEffect(() => {
    fetchHealth();
  }, [fetchHealth]);

  return {
    status,
    healthData,
    errorDetails,
    retry: fetchHealth,
  };
};
