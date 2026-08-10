import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { invoke } from '@tauri-apps/api/core'
import type { BatchQueueFile, BatchTask } from '../features/batch/batchTypes'

const emptyQueue: BatchQueueFile = { schemaVersion: 1, revision: 0, state: 'idle', activeTaskId: null, tasks: [] }
const BatchContext = createContext<{
  queue: BatchQueueFile
  loading: boolean
  error: string | null
  saveTask: (task: BatchTask) => Promise<BatchTask | null>
  enqueueTask: (taskId: string) => Promise<void>
  removeTask: (taskId: string) => Promise<void>
  startQueue: () => Promise<void>
  stopQueue: () => Promise<void>
  reload: () => Promise<void>
} | null>(null)

export function BatchProvider({ children }: { children: ReactNode }) {
  const [queue, setQueue] = useState<BatchQueueFile>(emptyQueue)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const reload = useCallback(async () => {
    setLoading(true)
    try {
      const next = await invoke<BatchQueueFile>('get_batch_queue')
      setQueue(next)
      setError(null)
    } catch (reason) {
      // Browser preview has no Tauri commands; keep the empty queue usable there.
      if (!(window as unknown as { __TAURI_INTERNALS__?: unknown }).__TAURI_INTERNALS__) setError(null)
      else setError(String(reason))
    } finally { setLoading(false) }
  }, [])

  useEffect(() => { void reload() }, [reload])
  useEffect(() => {
    if (queue.state !== 'running' && queue.state !== 'stopping') return
    const timer = window.setInterval(() => { void reload() }, 1000)
    return () => window.clearInterval(timer)
  }, [queue.state, reload])

  const saveTask = useCallback(async (task: BatchTask) => {
    try {
      const saved = await invoke<BatchTask>('save_batch_task', { task })
      await reload()
      return saved
    } catch (reason) { setError(String(reason)); return null }
  }, [reload])

  const enqueueTask = useCallback(async (taskId: string) => {
    try { setQueue(await invoke<BatchQueueFile>('enqueue_batch_task', { taskId })); setError(null) }
    catch (reason) { setError(String(reason)) }
  }, [])

  const removeTask = useCallback(async (taskId: string) => {
    try { setQueue(await invoke<BatchQueueFile>('remove_batch_task', { taskId })); setError(null) }
    catch (reason) { setError(String(reason)) }
  }, [])

  const startQueue = useCallback(async () => {
    try { setQueue(await invoke<BatchQueueFile>('start_batch_queue')); setError(null) }
    catch (reason) { setError(String(reason)) }
  }, [])

  const stopQueue = useCallback(async () => {
    try { setQueue(await invoke<BatchQueueFile>('stop_batch_queue')); setError(null) }
    catch (reason) { setError(String(reason)) }
  }, [])

  const value = useMemo(() => ({ queue, loading, error, saveTask, enqueueTask, removeTask, startQueue, stopQueue, reload }), [queue, loading, error, saveTask, enqueueTask, removeTask, startQueue, stopQueue, reload])
  return <BatchContext.Provider value={value}>{children}</BatchContext.Provider>
}

export function useBatch() {
  const value = useContext(BatchContext)
  if (!value) throw new Error('useBatch must be used inside BatchProvider')
  return value
}
