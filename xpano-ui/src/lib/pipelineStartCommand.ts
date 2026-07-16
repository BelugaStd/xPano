import type { ProjectRunOptions } from './types'

export function pipelineStartCommand(options: ProjectRunOptions) {
  return options.reconstruction ? 'start_reconstruction_job' : 'start_pipeline'
}
