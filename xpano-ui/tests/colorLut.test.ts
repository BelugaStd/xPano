import assert from 'node:assert/strict'
import test from 'node:test'
import {
  DJI_OSMO_360_DLOGM_REC709_PRESET,
  builtinColorLutPresetForSource,
  isCubeLutPath,
  isVideoTrackType,
  normalizeColorLutPath,
} from '../src/features/media/colorLut.ts'

test('color LUT is available only to video tracks', () => {
  assert.equal(isVideoTrackType('panoramic_video'), true)
  assert.equal(isVideoTrackType('ordinary_video'), true)
  assert.equal(isVideoTrackType('standard_photos'), false)
  assert.equal(isVideoTrackType('aerial_photos'), false)
})

test('color LUT paths normalize empty values and accept case-insensitive cube suffixes', () => {
  assert.equal(normalizeColorLutPath('  '), null)
  assert.equal(normalizeColorLutPath(' D:\\LUTs\\Restore.CUBE '), 'D:\\LUTs\\Restore.CUBE')
  assert.equal(isCubeLutPath('D:\\LUTs\\Restore.CUBE'), true)
  assert.equal(isCubeLutPath('D:\\LUTs\\Restore.png'), false)
})

test('only DJI OSV panorama imports opt into the bundled D-Log M restoration preset', () => {
  assert.equal(
    builtinColorLutPresetForSource('panoramic_video', 'D:\\captures\\DJI_0001.OSV'),
    DJI_OSMO_360_DLOGM_REC709_PRESET,
  )
  assert.equal(builtinColorLutPresetForSource('panoramic_video', 'D:\\captures\\VID_0001_00_0.insv'), null)
  assert.equal(builtinColorLutPresetForSource('ordinary_video', 'D:\\captures\\clip.mp4'), null)
})
