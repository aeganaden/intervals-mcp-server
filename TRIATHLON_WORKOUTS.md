# Triathlon Workout Files Tools

Two endpoints provide access to the local collection of triathlon workout JSON files:

1. **`get_triathlon_workout_files`** - Browse and search workouts
2. **`get_triathlon_workout_file_content`** - Get full workout data

## Tool 1: Browse and Search Workouts

```python
await get_triathlon_workout_files(
    category="Bike",         # Required: "Bike", "Run", or "Swim"
    sub_category="Aerobic",  # Optional: filter by workout type
    metric="HR"              # Optional: "HR", "Power", "Pace", or "Meters" (default: "HR")
)
```

## Tool 2: Get Full Workout Content

```python
await get_triathlon_workout_file_content(
    category="Swim",                    # Required: "Bike", "Run", or "Swim"
    metric="Meters",                    # Required: "HR", "Power", "Pace", or "Meters"
    filename="SRe1_Recovery_.json"      # Required: exact filename
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

### Browsing Workouts
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

### Getting Full Workout Data
```python
# Get complete JSON content of a swim recovery workout
content = await get_triathlon_workout_file_content("Swim", "Meters", "SRe1_Recovery_.json")

# Get bike aerobic interval workout
content = await get_triathlon_workout_file_content("Bike", "HR", "CAe11_Aerobic_Intervals_.json")

# Get running long run workout
content = await get_triathlon_workout_file_content("Run", "Pace", "RL1_Long_Run_.json")
```

## Response Formats

### `get_triathlon_workout_files` Response
Returns a formatted string containing:
- Number of files found
- For each workout file:
  - Filename
  - Duration in minutes
  - Target metric (HR/POWER/PACE/etc.)
  - Description excerpt

### `get_triathlon_workout_file_content` Response
Returns the complete JSON workout data as a formatted string, including:
- Full workout description
- Duration and distance
- Sport settings
- Training zones and targets
- Complete workout structure

## Error Handling

The endpoint validates input parameters and returns descriptive error messages for:
- Invalid categories
- Invalid metrics
- Non-existent sub-categories (with list of available options)
- Missing workout directories