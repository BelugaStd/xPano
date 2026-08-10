export type BatchQueueState = 'idle' | 'running' | 'stopping'
export type BatchTaskState = 'draft' | 'queued' | 'running' | 'completed' | 'failed' | 'cancelled' | 'interrupted'
export type BatchStageStatus = 'disabled' | 'pending' | 'running' | 'completed' | 'failed' | 'skipped'

export interface BatchStages { media: boolean; reconstruction: boolean; training: boolean }
export interface BatchStageStatuses { media: BatchStageStatus; reconstruction: BatchStageStatus; training: BatchStageStatus }
export interface BatchProgress { percent: number; message: string; current?: number | null; total?: number | null; etaSeconds?: number | null; elapsedSeconds: number }
export interface BatchError { code: string; stage?: string | null; message: string }
export interface BatchPipelineInput {
  mediaTrackIds: string[]
  reconstructionPlanId?: string | null
  reconstructionPythonExe?: string | null
  reconstructionScript?: string | null
  reconstructionArgs: string[]
  trainingConfig?: Record<string, unknown> | null
}
export interface BatchTask {
  taskId: string; projectId: string; projectRoot: string; label: string; order: number; configuredRevision: number
  stages: BatchStages; stageStatus: BatchStageStatuses; state: BatchTaskState; currentStage?: string | null
  stageJobIds: Record<string, unknown>; progress: BatchProgress; lastError?: BatchError | null
  pipeline: BatchPipelineInput; createdAt: string; startedAt?: string | null; finishedAt?: string | null; updatedAt: string
}
export interface BatchQueueFile { schemaVersion: number; revision: number; state: BatchQueueState; activeTaskId?: string | null; tasks: BatchTask[] }

export const emptyBatchStages = (): BatchStages => ({ media: true, reconstruction: true, training: true })
export const emptyBatchTask = (): BatchTask => {
  const now = new Date().toISOString()
  return {
    taskId: '', projectId: '', projectRoot: '', label: '', order: 0, configuredRevision: 0,
    stages: emptyBatchStages(),
    stageStatus: { media: 'pending', reconstruction: 'pending', training: 'pending' },
    state: 'draft', currentStage: null, stageJobIds: {},
    progress: { percent: 0, message: '', current: null, total: null, etaSeconds: null, elapsedSeconds: 0 },
    lastError: null, pipeline: { mediaTrackIds: [], reconstructionArgs: [], trainingConfig: null },
    createdAt: now, startedAt: null, finishedAt: null, updatedAt: now,
  }
}

export function validateStagePrefix(stages: BatchStages): string | null {
  if (stages.reconstruction && !stages.media) return '开启对齐前必须先开启素材准备'
  if (stages.training && !stages.reconstruction) return '开启训练前必须先开启对齐'
  return null
}

export function enabledStageCount(stages: BatchStages) {
  return Number(stages.media) + Number(stages.reconstruction) + Number(stages.training)
}
