'use client'

import { useEffect, useRef } from 'react'

/**
 * 모바일 당겨서 새로고침(pull-to-refresh) 제스처를 감지하는 훅
 * 스크롤이 최상단일 때 threshold(px) 이상 아래로 당기면 onRefresh 호출
 */
export function usePullToRefresh(onRefresh: () => void, threshold = 80) {
  const startY = useRef(0)
  const pulling = useRef(false)

  useEffect(() => {
    const onTouchStart = (e: TouchEvent) => {
      // 페이지 최상단일 때만 pull 감지
      if (window.scrollY === 0) {
        startY.current = e.touches[0].clientY
        pulling.current = true
      }
    }

    const onTouchEnd = (e: TouchEvent) => {
      if (!pulling.current) return
      const delta = e.changedTouches[0].clientY - startY.current
      if (delta > threshold) onRefresh()
      pulling.current = false
    }

    document.addEventListener('touchstart', onTouchStart, { passive: true })
    document.addEventListener('touchend', onTouchEnd, { passive: true })

    return () => {
      document.removeEventListener('touchstart', onTouchStart)
      document.removeEventListener('touchend', onTouchEnd)
    }
  }, [onRefresh, threshold])
}
