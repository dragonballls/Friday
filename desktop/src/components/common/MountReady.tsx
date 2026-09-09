import { useEffect } from 'react'

export function MountReady() {
  useEffect(() => {
    window.dispatchEvent(new Event('friday:ready'))
  }, [])
  return null
}