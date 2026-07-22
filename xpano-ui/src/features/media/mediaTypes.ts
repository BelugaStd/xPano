import type { MediaImportDraftInput, ProjectTrackType } from '../../lib/contracts'
import { builtinColorLutPresetForSource, isCubeLutPath, isStyleLutSupported } from './colorLut'

export interface ImportPathInfo {
  path: string
  label: string
  name: string
  isDir: boolean
  extension: string
  suggestedType: ProjectTrackType | 'unsupported'
  kind: ProjectTrackType | 'unsupported'
  validPhotoFolder: boolean
  valid: boolean
  photoCount: number
  previewPaths: string[]
  message: string
}

export interface MediaImportDraft extends MediaImportDraftInput {
  id: string
  info: ImportPathInfo
  duration: number
}

export function allowedTrackTypes(info: ImportPathInfo): ProjectTrackType[] {
  const extension = info.extension.toLowerCase()
  if (extension === 'osv' || extension === 'insv') return ['panoramic_video']
  if (['mp4', 'mov', 'avi', 'mkv', 'm4v', 'webm'].includes(extension)) return ['ordinary_video']
  if (info.isDir || ['jpg', 'jpeg', 'png', 'tif', 'tiff', 'bmp', 'webp'].includes(extension)) {
    return ['standard_photos', 'aerial_photos']
  }
  return []
}

export function isDraftValid(draft: MediaImportDraft) {
  const allowedPreset = builtinColorLutPresetForSource(draft.trackType, draft.sourcePath)
  return draft.info.valid
    && allowedTrackTypes(draft.info).includes(draft.trackType)
    && Boolean(draft.label.trim())
    && Number.isFinite(draft.extraction.framesPerSecond)
    && draft.extraction.framesPerSecond > 0
    && (!draft.extraction.styleLutPath || isCubeLutPath(draft.extraction.styleLutPath))
    && (!draft.extraction.colorLutPreset || draft.extraction.colorLutPreset === allowedPreset)
    && (!draft.extraction.styleLutPath || isStyleLutSupported(draft.trackType))
}
