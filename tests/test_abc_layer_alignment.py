"""Unit tests for ABC multi-layer measure-time alignment.

When some measures of a voice have `&`-separated layers but earlier (or later)
measures don't, `split_into_layered_measures` previously emitted layers whose
leading "empty" slots took zero time. That made layer N's first/last notes
appear to be at time 0 even when they only musically appeared several measures
in — breaking first-pitch (which picked the highest across layers regardless
of when they actually started) and last-pitch (which compared end-times that
were off by the leading empty-measure duration).

The fix pads empty layer slots with a measure-long rest (`x{units_per_measure}`)
and makes `get_first_pitch_for_voices` time-aware so a later-starting layer
never displaces a true opening note.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from answer_extraction.abc.utils import (
    parse_units_per_measure,
    split_into_layered_measures,
    get_first_pitch_for_voices,
    get_last_pitch_for_voices,
    _extract_notes_with_timing,
    parse_key_signature,
    parse_unit_note_length,
)


def _make_abc(meter: str, unit: str, key: str, body_lines: list[str]) -> str:
    header = (
        f"X: 1\n"
        f"L: {unit}\n"
        f"M: {meter}\n"
        f"K: {key}\n"
        "%%staves {1 2}\n"
        "V: 1 clef=treble\n"
        "V: 2 clef=bass\n"
    )
    return header + "\n".join(body_lines) + "\n"


def test_units_per_measure_basic():
    assert parse_units_per_measure("M:3/4\nL:1/8\n") == 6
    assert parse_units_per_measure("M:2/4\nL:1/16\n") == 8
    assert parse_units_per_measure("M:6/8\nL:1/8\n") == 6
    assert parse_units_per_measure("M:4/4\nL:1/4\n") == 4


def test_split_pads_missing_layer_slots():
    # Two measures: first has no `&`, second has `& E`. With padding, layer 1
    # of measure 1 becomes `x6` (a measure-rest), preserving timing.
    layers = split_into_layered_measures("ABC | DEF & GAB", units_per_measure=6)
    assert layers[0] == "ABC | DEF "
    assert layers[1] == "x6| GAB"


def test_split_without_padding_keeps_old_behavior():
    # Counters that don't care about time should still see empty placeholders.
    layers = split_into_layered_measures("ABC | DEF & GAB")
    assert layers[0] == "ABC | DEF "
    assert layers[1] == "| GAB"


def test_first_pitch_ignores_late_starting_layer():
    # Layer 1 only appears in measure 5; its first note (C5) must NOT be
    # picked as the passage's first pitch over layer 0's actual opening (G#4).
    abc = _make_abc(
        "3/4", "1/8", "A",
        [
            "[V:1] G/B/e/g/b4 |",
            "[V:1] b/a/g/f/ f/e/^d/c/ B/A/G/A/ |",
            "[V:1] G/B/A/G/ A/B/c/^d/ e/f/g/a/ |",
            "[V:1] b/c'/^d'/e'/ d'/c'/b/a/ g/f/e/^d/ |",
            "[V:1] x4gf & cz/c'/e2^d2 |",
        ],
    )
    assert get_first_pitch_for_voices(abc, ["1"]) == "G#4"


def test_last_pitch_uses_padded_layer_time():
    # Layer 1 starts in measure 7 (after 6 empty measures). Without padding,
    # its B5 looks like it ends at relative time 4; with padding (6 * 2qtr
    # for M:2/4) the B5 is at absolute time ~16, beating layer 0's earlier
    # C5 end-time of 14.5.
    abc = _make_abc(
        "2/4", "1/16", "C",
        [
            "[V:1] {/ab} c'2c'>c' c'2 b/a/g/f/ |",
            "[V:1] e2!trill!fe/f/ g2 z2 |",
            "[V:1] {/ab} c'2c'>c' c'2 b/a/g/f/ |",
            "[V:1] .ec'/d'/ e'/d'/c'/b/ a/g/f/e/ d/c/B/A/ |",
            "[V:1] G2F4E2 |",
            "[V:1] z .D.FA ^cdfa |",
            "[V:1] a=cc4ed & x6B2 |",
            "[V:1] c2x6 & c2 z2 gec'.b |",
        ],
    )
    assert get_last_pitch_for_voices(abc, ["1"]) == "B5"


def test_grace_notes_at_time_zero_keep_first_grace_as_first():
    # `{/ab} c'` -> grace `a` is the first event. Existing semantics (the
    # docstring: "Grace notes count as first/last notes if at those
    # positions") are preserved by the time-aware rewrite.
    abc = _make_abc("2/4", "1/16", "C", ["[V:1] {/ab} c'4 |"])
    assert get_first_pitch_for_voices(abc, ["1"]) == "A5"


def test_simultaneous_layers_at_time_zero_pick_highest():
    # Both layers start at time 0 (the measure opens with `& `). Highest wins.
    abc = _make_abc("2/4", "1/4", "C", ["[V:1] C & e |"])
    assert get_first_pitch_for_voices(abc, ["1"]) == "E5"


def test_note_timing_records_start_and_end():
    # Sanity: NoteWithTiming exposes both start_time and end_time, and they
    # advance monotonically across sequential notes.
    ks = parse_key_signature("K:C\n")
    notes = _extract_notes_with_timing("CDE", ks, unit_length=1.0)
    assert [n.pitch for n in notes] == ["C4", "D4", "E4"]
    assert [n.start_time for n in notes] == [0.0, 1.0, 2.0]
    assert [n.end_time for n in notes] == [1.0, 2.0, 3.0]
