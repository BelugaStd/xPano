import assert from 'node:assert/strict'
import test from 'node:test'
import { pipelineStartCommand } from '../src/lib/pipelineStartCommand.ts'

test('reconstruction jobs use the plan-validated backend command', () => {
  assert.equal(pipelineStartCommand({
    reconstruction: {
      projectRoot: 'D:/project',
      expectedRevision: 7,
      planId: 'plan-1',
    },
  }), 'start_reconstruction_job')
})

test('legacy non-project pipeline starts retain the generic command', () => {
  assert.equal(pipelineStartCommand({}), 'start_pipeline')
})
