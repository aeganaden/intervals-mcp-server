import json
from pathlib import Path

BASE_DIR = Path(__file__).parent

# Map folder name fragments to top-level sport keys
SPORT_FOLDERS = {
    "Bike": "bike",
    "Run": "run",
    "Swim": "swim",
}


def infer_sport_from_folder(folder: Path) -> str | None:
    for key, sport in SPORT_FOLDERS.items():
        if key in folder.name:
            return sport
    return None


def infer_subcategory_from_filename(filename: str) -> str | None:
    """Infer a short subcategory code from a workout filename.

    Examples
    --------
    CAe11_Aerobic_Intervals_.json -> "cae"
    CAP1_Aerobic_Progression_Ride_80_20_Endurance_.json -> "cap"
    ER10_Endurance_Run_.json -> "er"
    SAe1_Aerobic_Intervals_.json -> "sae"
    """
    stem = filename.rsplit(".", 1)[0]

    # Take leading alpha characters (ignore digits and underscores that follow)
    prefix_chars = []
    for ch in stem:
        if ch.isalpha():
            prefix_chars.append(ch)
        else:
            break

    if not prefix_chars:
        return None

    prefix = "".join(prefix_chars)

    # Normalise to lowercase to use as key (e.g. "CAe" -> "cae")
    return prefix.lower()


def extract_description_from_file(path: Path) -> str | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

    desc = data.get("description")
    if not isinstance(desc, str):
        return None

    text = desc.strip()
    if not text:
        return None

    # Many descriptions have the format:
    #   "<workout steps>\n`- - - -\n<intention/overview text>"
    # We only want the intention/overview part after the marker.
    marker = "`- - - -"
    if marker in text:
        _, after = text.split(marker, 1)
        cleaned = after.strip()
        if cleaned:
            return cleaned

    # Fallback: if no marker, strip obvious workout step lines
    # such as "5:00 in Zone 1", "10 minutes Z2", distances, etc.
    lines = text.splitlines()

    def looks_like_step(line: str) -> bool:
        l = line.strip().lower()
        if not l:
            return False
        # Common patterns: time + "in zone", "z1", repetitions, distances
        keywords = [
            "zone 1",
            "zone 2",
            "zone 3",
            "zone 4",
            "zone 5",
            "zone x",
            "z1",
            "z2",
            "z3",
            "z4",
            "z5",
            "km",
            "k m",
            "mile",
            "miles",
            "x (",
            "x (",
            "rest",
        ]
        has_digit = any(ch.isdigit() for ch in l)
        return has_digit and any(k in l for k in keywords)

    non_step_lines = [ln for ln in lines if not looks_like_step(ln)]
    cleaned = "\n".join(non_step_lines).strip()
    if cleaned:
        return cleaned

    # If everything looks like workout instructions, treat this file as having
    # no usable description so that other files with the same prefix (that do
    # have a narrative section or delimiter) can be used instead.
    return None


def format_duration(total_seconds: int) -> str:
    """Format a duration in seconds as "Hh Mm Ss".

    Examples
    --------
    2600 -> "0h 43m 20s"
    """

    if total_seconds < 0:
        return "0h 00m 00s"

    hours = total_seconds // 3600
    remainder = total_seconds % 3600
    minutes = remainder // 60
    seconds = remainder % 60
    return f"{hours}h {minutes:02d}m {seconds:02d}s"


def build_consolidated_descriptions() -> dict:
    # Nested structure:
    # {
    #   "bike": {
    #       "ca": {
    #           "description": "...",
    #           "workouts": {
    #               "ca6_accelerations_ride": {"duration": "01h 05m 00s"},
    #               ...
    #           },
    #       },
    #       ...
    #   },
    #   ...
    # }
    result: dict[str, dict[str, dict[str, object]]] = {}

    for folder in BASE_DIR.iterdir():
        if not folder.is_dir():
            continue

        sport = infer_sport_from_folder(folder)
        if sport is None:
            continue

        sport_map = result.setdefault(sport, {})

        # Group all files by their inferred subcategory prefix first so that
        # we can search across multiple workouts sharing the same code.
        grouped: dict[str, list[Path]] = {}
        for file in folder.glob("*.json"):
            subcat = infer_subcategory_from_filename(file.name)
            if subcat is None:
                continue
            grouped.setdefault(subcat, []).append(file)

        for subcat, files in grouped.items():
            # Already have data for this subcategory from another folder
            if subcat in sport_map:
                # Still append any new workouts for this subcategory
                subcat_entry = sport_map[subcat]
                workouts = subcat_entry.setdefault("workouts", {})  # type: ignore[assignment]

                for f in files:
                    try:
                        data = json.loads(f.read_text(encoding="utf-8"))
                    except Exception:
                        continue

                    duration = data.get("duration")
                    distance = data.get("distance")
                    if isinstance(duration, (int, float)):
                        workout_key = f.stem.lower()
                        # Distance is often 0.0 or absent; represent missing/non-positive as "-".
                        if isinstance(distance, (int, float)) and distance > 0:
                            # distance is in meters; convert to kilometers string like "6.5km"
                            km_value = distance / 1000.0
                            # Avoid excessive decimals but preserve typical .0/.5 precision
                            distance_str: str = f"{km_value:.1f}km".rstrip("0").rstrip(".") + "km" if False else f"{km_value:.1f}km"
                        else:
                            distance_str = "-"

                        workouts[workout_key] = {
                            "duration": format_duration(int(duration)),
                            "distance": distance_str,
                        }

                continue

            chosen_desc: str | None = None
            workouts: dict[str, dict[str, str]] = {}

            # First pass: look for a file that yields a non-empty, non-step-only
            # description. Because extract_description_from_file already tries
            # to strip step-like lines, we just need a non-None result.
            for f in files:
                desc = extract_description_from_file(f)
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                except Exception:
                    data = None

                if data is not None:
                    duration = data.get("duration")
                    distance = data.get("distance")
                    if isinstance(duration, (int, float)):
                        workout_key = f.stem.lower()
                        if isinstance(distance, (int, float)) and distance > 0:
                            km_value = distance / 1000.0
                            distance_str = f"{km_value:.1f}km"
                        else:
                            distance_str = "-"

                        workouts[workout_key] = {
                            "duration": format_duration(int(duration)),
                            "distance": distance_str,
                        }

                if chosen_desc is None and desc is not None:
                    chosen_desc = desc

            # If *no* file for this subcategory produced a useful description,
            # skip this subcategory entirely instead of storing raw workout steps.
            if chosen_desc is None:
                continue

            sport_map[subcat] = {
                "description": chosen_desc,
                "workouts": workouts,
            }

    return result


def main() -> None:
    consolidated = build_consolidated_descriptions()
    out_path = BASE_DIR / "category_descriptions.json"
    out_path.write_text(json.dumps(consolidated, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {out_path} with {sum(len(v) for v in consolidated.values())} subcategories.")


if __name__ == "__main__":
    main()
