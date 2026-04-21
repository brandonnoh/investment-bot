import useSWR from 'swr'

const fetcher = (url: string) => fetch(url).then(r => r.json())

export function useWealthData() {
  const { data, error, mutate } = useSWR('/api/wealth', fetcher, { refreshInterval: 60000 })
  return { data, isLoading: !data && !error, mutate }
}
