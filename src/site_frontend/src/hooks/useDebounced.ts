import { useEffect, useState } from 'react'

/** `value` só "assenta" depois de `ms` sem mudar: evita uma chamada à API por tecla. */
export function useDebounced<T>(value: T, ms: number): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), ms)
    return () => clearTimeout(id)
  }, [value, ms])
  return debounced
}
