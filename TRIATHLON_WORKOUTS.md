# Triathlon Workout Files Endpoint

The `get_triathlon_workout_files` endpoint provides access to the local collection of triathlon workout JSON files.

## Usage

```python
await get_triathlon_workout_files(
    category="Bike",         # Required: "Bike", "Run", or "Swim"
    sub_category="Aerobic",  # Optional: filter by workout type
    metric="HR"              # Optional: "HR", "Power", "Pace", or "Meters" (default: "HR")
)
```

## Parameters

- **category** (required): The sport category
  - `"Bike"` - Cycling workouts
  - `"Run"` - Running workouts  
  - `"Swim"` - Swimming workouts

- **metric** (optional, default: "HR"): The measurement type
  - `"HR"` - Heart rate based workouts
  - `"Power"` - Power based workouts (cycling)
  - `"Pace"` - Pace based workouts (running)
  - `"Meters"` - Distance based workouts (swimming)

- **sub_category** (optional): Filter by workout type
  - `"aerobic"` - Aerobic intervals and progression
  - `"anaerobic"` - Anaerobic intervals
  - `"accelerations"` - Acceleration workouts
  - `"cruise"` - Cruise intervals
  - `"critical_power"` - Critical power workouts
  - `"foundation"` - Foundation/base workouts
  - `"recovery"` - Recovery workouts
  - `"tempo"` - Tempo workouts
  - `"threshold"` - Threshold workouts
  - And many more...

## Examples

```python
# Get all bike workouts with heart rate
result = await get_triathlon_workout_files(category="Bike", metric="HR")

# Get bike power-based aerobic workouts
result = await get_triathlon_workout_files(
    category="Bike", 
    sub_category="aerobic", 
    metric="Power"
)

# Get running pace-based workouts
result = await get_triathlon_workout_files(category="Run", metric="Pace")
```

## Response Format

The endpoint returns a formatted string containing:
- Number of files found
- For each workout file:
  - Filename
  - Duration in minutes
  - Target metric (HR/POWER/PACE/etc.)
  - Description excerpt
  - Full workout data (JSON structure)

## Error Handling

The endpoint validates input parameters and returns descriptive error messages for:
- Invalid categories
- Invalid metrics
- Non-existent sub-categories (with list of available options)
- Missing workout directories