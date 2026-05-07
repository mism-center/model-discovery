import { useState, useEffect } from 'react';
import {
  fetchSearchResults,
  type SearchQuery,
  type SearchResponse,
} from '~/api/services/search';

export function useSearchQuery(searchQuery: SearchQuery) {
  const [data, setData] = useState<SearchResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let isMounted = true;
    setIsLoading(true);

    fetchSearchResults(searchQuery)
      .then((response) => {
        if (isMounted) {
          setData(response);
          setError(null);
        }
      })
      .catch((error: unknown) => {
        if (isMounted) setError(error as Error);
      })
      .finally(() => {
        if (isMounted) setIsLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [searchQuery]);

  return { data, isLoading, error };
}
