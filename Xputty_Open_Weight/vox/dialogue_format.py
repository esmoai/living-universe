"""Keep generated timing fields separate from spoken text."""

import re


def raw_prompt(text, context=""):
    return (
        context
        + "<|segment|><|at_ms|>0<|delta_ms|>0<|text|>"
        + text.strip()
        + "\n<|segment|>"
    )


def parse_raw_generation(text):
    segments = []
    invalid = []
    for part in text.replace("<|eod|>", "").split("<|segment|>"):
        if not part.strip():
            continue
        match = re.fullmatch(
            r"\s*(?:<\|at_ms\|>(\d+))?(?:<\|delta_ms\|>(\d+))?<\|text\|>(.*?)\s*",
            part,
            re.S,
        )
        if not match or "<|" in match.group(3):
            invalid.append(part)
            continue
        at, delta, words = match.groups()
        segments.append(
            {
                "text": words.strip(),
                "source_start_ms": int(at) if at else None,
                "source_start_delta_ms": int(delta) if delta else None,
            }
        )
    return {
        "segments": segments,
        "speech_text": "\n".join(s["text"] for s in segments if s["text"]),
        "timing_fields_valid": bool(segments) and not invalid,
        "invalid_segments": len(invalid),
        "delivery_schedule_validated": False,
        "timing_scope": "Generated source-segment positions; not verified delivery pauses",
    }
