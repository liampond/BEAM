"""Utilities for analyzing passages in MusicXML scores."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Dict, Iterable, List, Optional
import xml.etree.ElementTree as ET

_STEP_TO_SEMITONE = {
    "C": 0,
    "D": 2,
    "E": 4,
    "F": 5,
    "G": 7,
    "A": 9,
    "B": 11,
}

_ALTER_TO_SYMBOL = {
    -2: "bb",
    -1: "b",
    0: "",
    1: "#",
    2: "##",
}

_NOTE_TYPE_LABELS = {
    "long": "Long",
    "breve": "Breve",
    "whole": "Whole",
    "half": "Half",
    "quarter": "Quarter",
    "eighth": "Eighth",
    "16th": "Sixteenth",
    "32nd": "Thirty-second",
    "64th": "Sixty-fourth",
    "128th": "Hundred twenty-eighth",
    "256th": "Two hundred fifty-sixth",
}


@dataclass(frozen=True)
class NoteEvent:
    """A single musical event extracted from MusicXML."""

    staff: int
    voice: str
    is_rest: bool
    time: int
    duration_divs: int
    step: Optional[str]
    alter: int
    octave: Optional[int]
    note_type: Optional[str]
    dots: int
    is_grace: bool
    midi: Optional[int]
    order: int
    divisions: int

    def with_time_offset(self, offset: int, order_offset: int) -> "NoteEvent":
        """Return a copy of this event with a time offset."""

        return replace(self, time=self.time + offset, order=self.order + order_offset)


@dataclass(frozen=True)
class MeasureData:
    """Container for all events within a single measure."""

    number: int
    events: List[NoteEvent]

    @property
    def length_divs(self) -> int:
        """Return the measure length in MusicXML divisions."""

        if not self.events:
            return 0
        return max(ev.time + ev.duration_divs for ev in self.events)


class MusicXMLAnalyzer:
    """Parse a MusicXML part and expose per-measure musical events."""

    def __init__(self, file_path: Path) -> None:
        if not file_path.exists():
            raise FileNotFoundError(f"MusicXML file not found: {file_path}")

        self.file_path = file_path
        self._measures: Dict[int, MeasureData] = {}

        tree = ET.parse(file_path)
        root = tree.getroot()
        part = root.find("part")
        if part is None:
            raise ValueError(f"No <part> element found in {file_path}")

        current_divisions = 1
        for measure_el in part.findall("measure"):
            number_attr = measure_el.get("number")
            try:
                number = int(number_attr) if number_attr is not None else None
            except ValueError:
                # Skip non-numeric measure identifiers (e.g., repeats)
                continue
            if number is None:
                continue

            measure_data, current_divisions = self._parse_measure(measure_el, number, current_divisions)
            self._measures[number] = measure_data

    def get_measure(self, number: int) -> MeasureData:
        if number not in self._measures:
            raise ValueError(f"Measure {number} not found in {self.file_path.name}")
        return self._measures[number]

    def get_measure_range(self, start: int, end: int) -> List[NoteEvent]:
        if end < start:
            raise ValueError("End measure must be >= start measure")

        combined: List[NoteEvent] = []
        time_offset = 0
        order_offset = 0
        for number in range(start, end + 1):
            measure = self.get_measure(number)
            combined.extend(ev.with_time_offset(time_offset, order_offset) for ev in measure.events)
            time_offset += measure.length_divs
            order_offset += len(measure.events)
        return combined

    def _parse_measure(self, measure_el: ET.Element, number: int, current_divisions: int) -> tuple[MeasureData, int]:
        events: List[NoteEvent] = []
        current_time = 0
        order = 0
        last_time_per_voice: Dict[tuple[int, str], int] = {}

        for child in measure_el:
            tag = child.tag

            if tag == "attributes":
                divisions_el = child.find("divisions")
                if divisions_el is not None and divisions_el.text:
                    current_divisions = int(divisions_el.text)
            elif tag == "note":
                # Skip invisible notes (print-object="no")
                print_object = child.get("print-object")
                if print_object == "no":
                    continue
                
                staff = int(child.findtext("staff", default="1"))
                voice = child.findtext("voice", default="1")
                duration_text = child.findtext("duration")
                duration = int(duration_text) if duration_text else 0
                is_chord = child.find("chord") is not None
                is_rest = child.find("rest") is not None
                is_grace = child.find("grace") is not None

                start_time = last_time_per_voice.get((staff, voice), current_time) if is_chord else current_time

                step = None
                alter = 0
                octave = None
                note_type = child.findtext("type")
                dots = len(child.findall("dot"))

                if not is_rest:
                    pitch_el = child.find("pitch")
                    if pitch_el is not None:
                        step = pitch_el.findtext("step")
                        alter_text = pitch_el.findtext("alter")
                        alter = int(alter_text) if alter_text else 0
                        octave_text = pitch_el.findtext("octave")
                        octave = int(octave_text) if octave_text else None

                midi = None
                if step and octave is not None:
                    midi = _step_to_midi(step, alter, octave)

                events.append(
                    NoteEvent(
                        staff=staff,
                        voice=voice,
                        is_rest=is_rest,
                        time=start_time,
                        duration_divs=duration,
                        step=step,
                        alter=alter,
                        octave=octave,
                        note_type=note_type,
                        dots=dots,
                        is_grace=is_grace,
                        midi=midi,
                        order=order,
                        divisions=current_divisions,
                    )
                )

                last_time_per_voice[(staff, voice)] = start_time
                if not is_chord:
                    current_time += duration
                order += 1
            elif tag == "backup":
                duration_text = child.findtext("duration")
                duration = int(duration_text) if duration_text else 0
                current_time -= duration
            elif tag == "forward":
                duration_text = child.findtext("duration")
                duration = int(duration_text) if duration_text else 0
                current_time += duration

        return MeasureData(number=number, events=events), current_divisions


def _step_to_midi(step: str, alter: int, octave: int) -> int:
    base = _STEP_TO_SEMITONE.get(step.upper())
    if base is None:
        raise ValueError(f"Unexpected pitch step: {step}")
    return (octave + 1) * 12 + base + alter


def format_pitch(step: Optional[str], alter: int, octave: Optional[int]) -> str:
    if step is None or octave is None:
        raise ValueError("Cannot format pitch without step and octave")

    symbol = _ALTER_TO_SYMBOL.get(alter)
    if symbol is None:
        # Fall back to repeated symbols for larger alterations
        if alter > 0:
            symbol = "#" * alter
        else:
            symbol = "b" * (-alter)
    return f"{step}{symbol}{octave}"


def format_note_value(note_type: Optional[str], dots: int) -> str:
    if not note_type:
        return "Unknown"

    base = _NOTE_TYPE_LABELS.get(note_type, note_type.capitalize())
    base_lower = base.lower()

    if dots == 0:
        return f"{base} note"
    if dots == 1:
        return f"Dotted {base_lower} note"
    if dots == 2:
        return f"Double-dotted {base_lower} note"
    return f"Triple-dotted {base_lower} note" if dots == 3 else f"{dots}-dotted {base_lower} note"


def select_first_note(events: Iterable[NoteEvent], staff: int) -> NoteEvent:
    candidates = [ev for ev in events if ev.staff == staff and not ev.is_rest]
    if not candidates:
        raise ValueError(f"No notes found on staff {staff}")

    candidates.sort(key=lambda ev: (ev.time, ev.order))
    earliest_time = candidates[0].time
    earliest = [ev for ev in candidates if ev.time == earliest_time]
    earliest.sort(key=lambda ev: (ev.midi or -9999, ev.order))
    return earliest[-1]


def select_last_note(events: Iterable[NoteEvent], staff: int) -> NoteEvent:
    candidates = [ev for ev in events if ev.staff == staff and not ev.is_rest]
    if not candidates:
        raise ValueError(f"No notes found on staff {staff}")

    candidates.sort(key=lambda ev: (ev.time, ev.order))
    latest_time = candidates[-1].time
    latest = [ev for ev in candidates if ev.time == latest_time]
    latest.sort(key=lambda ev: (ev.midi or -9999, ev.order))
    return latest[-1]


def count_pitch_classes(events: Iterable[NoteEvent], staff: int) -> int:
    pitch_classes = {
        (ev.midi % 12)
        for ev in events
        if ev.staff == staff and not ev.is_rest and ev.midi is not None
    }
    return len(pitch_classes)


def longest_note_duration_beats(events: Iterable[NoteEvent]) -> float:
    durations = [
        ev.duration_divs / ev.divisions
        for ev in events
        if not ev.is_rest and ev.duration_divs > 0 and ev.divisions > 0
    ]
    return max(durations) if durations else 0.0


def count_rests(events: Iterable[NoteEvent]) -> int:
    return sum(1 for ev in events if ev.is_rest)


def format_beats(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    # Avoid floating point noise by rounding to 3 decimal places and stripping zeros
    rounded = round(value, 3)
    return f"{rounded}".rstrip("0").rstrip(".")


def select_lowest_note(events: Iterable[NoteEvent], staff: int) -> NoteEvent:
    candidates = [ev for ev in events if ev.staff == staff and not ev.is_rest and ev.midi is not None]
    if not candidates:
        raise ValueError(f"No notes found on staff {staff}")

    candidates.sort(key=lambda ev: (ev.midi, ev.time, ev.order))
    return candidates[0]
