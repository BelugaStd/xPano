import assert from 'node:assert/strict'
import test from 'node:test'
import { batchOverallPercent, enabledStageCount, setBatchStage, validateStagePrefix, type BatchTask } from '../src/features/batch/batchTypes.ts'

test('batch stages only allow a contiguous prefix', () => {
  assert.equal(validateStagePrefix({ media: true, reconstruction: true, training: true }), null)
  assert.equal(validateStagePrefix({ media: true, reconstruction: false, training: true }), '开启训练前必须先开启对齐')
  assert.equal(validateStagePrefix({ media: false, reconstruction: true, training: false }), '开启对齐前必须先开启素材准备')
  assert.equal(validateStagePrefix({ media: false, reconstruction: false, training: false }), '请至少开启素材准备阶段')
  assert.equal(enabledStageCount({ media: true, reconstruction: false, training: false }), 1)
})

test('turning off an earlier batch stage also turns off every dependent stage', () => {
  assert.deepEqual(
    setBatchStage({ media: true, reconstruction: true, training: true }, 'media', false),
    { media: false, reconstruction: false, training: false },
  )
  assert.deepEqual(
    setBatchStage({ media: true, reconstruction: true, training: true }, 'reconstruction', false),
    { media: true, reconstruction: false, training: false },
  )
})

test('terminal tasks count as consumed queue work even when a stage failed early', () => {
  const task = (state: BatchTask['state'], percent: number) => ({ state, progress: { percent } }) as BatchTask
  assert.equal(batchOverallPercent([task('completed', 100), task('failed', 22), task('queued', 0)]), 200 / 3)
  assert.equal(batchOverallPercent([]), 0)
})
