import assert from 'node:assert/strict'
import test from 'node:test'
import { enabledStageCount, validateStagePrefix } from '../src/features/batch/batchTypes.ts'

test('batch stages only allow a contiguous prefix', () => {
  assert.equal(validateStagePrefix({ media: true, reconstruction: true, training: true }), null)
  assert.equal(validateStagePrefix({ media: true, reconstruction: false, training: true }), '开启训练前必须先开启对齐')
  assert.equal(validateStagePrefix({ media: false, reconstruction: true, training: false }), '开启对齐前必须先开启素材准备')
  assert.equal(enabledStageCount({ media: true, reconstruction: false, training: false }), 1)
})
