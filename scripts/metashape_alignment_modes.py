ALIGNMENT_MODE_BACKBONE = "backbone"
ALIGNMENT_MODE_MIXED = "mixed"
SUPPORTED_ALIGNMENT_MODES = {ALIGNMENT_MODE_BACKBONE, ALIGNMENT_MODE_MIXED}


def normalize_alignment_mode(value):
    raw = str(value or ALIGNMENT_MODE_BACKBONE).strip().lower()
    aliases = {
        "backbone": ALIGNMENT_MODE_BACKBONE,
        "staged": ALIGNMENT_MODE_BACKBONE,
        "stage": ALIGNMENT_MODE_BACKBONE,
        "骨架": ALIGNMENT_MODE_BACKBONE,
        "mixed": ALIGNMENT_MODE_MIXED,
        "legacy": ALIGNMENT_MODE_MIXED,
        "混合": ALIGNMENT_MODE_MIXED,
    }
    mode = aliases.get(raw, raw)
    if mode not in SUPPORTED_ALIGNMENT_MODES:
        supported = ", ".join(sorted(SUPPORTED_ALIGNMENT_MODES))
        raise ValueError(f"Unsupported Metashape alignment mode: {value}. Supported: {supported}")
    return mode
