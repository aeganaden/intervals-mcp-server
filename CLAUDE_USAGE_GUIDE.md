# Claude Usage Guide - Triathlon Workout Files

This guide explains how Claude should use the triathlon workout file tools to access and work with the 2,400+ workout files.

## Typical Workflow

### 1. Browse Available Workouts
First, use `get_triathlon_workout_files` to see what's available:

```python
# Browse all swim workouts
result = await get_triathlon_workout_files("Swim", metric="Meters")

# Find specific type of bike workouts
result = await get_triathlon_workout_files("Bike", "aerobic", "Power")

# Look for running recovery workouts
result = await get_triathlon_workout_files("Run", "recovery", "HR")
```

### 2. Get Readable Workout Format (Recommended)
When you find an interesting workout from step 1, parse it into readable format:

```python
# From the browse results, you see "SRe1_Recovery_.json" looks interesting
readable = await parse_triathlon_workout_to_readable_format("Swim", "Meters", "SRe1_Recovery_.json")

# Now you have a beautifully formatted workout with intervals, zones, and instructions
```

### 3. Get Full Workout Content (Advanced)
If you need the raw JSON data for detailed analysis:

```python
content = await get_triathlon_workout_file_content("Swim", "Meters", "SRe1_Recovery_.json")

# Now you have the complete JSON with all workout details
```

## Handling File Paths

**Important**: Claude, you no longer need to access files at paths like `/mnt/data/workout_files/Swim/Meters/Recovery/SRe1_Recovery_.json`. 

Instead:
1. Use `get_triathlon_workout_files` to find workout filenames
2. Use `get_triathlon_workout_file_content` with the exact filename

## Sport-Specific Sub-Categories

Each sport has different available sub-categories. If you request a non-existent sub-category, you'll get a helpful error message with available options.

### Bike Sub-Categories (26 available)
aerobic, anaerobic, accelerations, cruise, critical_power, depletion, descending, foundation, fast_finish, force, mixed, sprint, progression, power_repetitions, recovery, speed_play, speed_repetitions, steady_state, tempo, threshold, time_trial, variable_intensity, vo2max, endurance, easy, lactate, over_under

### Run Sub-Categories (30 available)  
aerobic, anaerobic, accelerations, cruise, critical_velocity, depletion, descending, foundation, fast_finish, fartlek, half_marathon, heart_rate, long, long_speedplay, mixed, marathon_pace, progression, progression_fartlek, progression_intervals, recovery, short_intervals, speed_play, steady_state, tempo, time_trial, variable_intensity, vo2max, cross_training, 5k, 10k, easy, easy_fast_finish, long_finish, long_intervals, outdoor, warmup

### Swim Sub-Categories (17 available)
aerobic, broken_swims, cruise, critical_pace, endurance, easy_endurance, endurance_recovery, foundation, short_intervals, lactate, mixed, recovery, short_sprint, speed_play, tempo, threshold_intervals, time_trial

## Examples for Common Requests

### "I want a swim recovery workout"
```python
# Step 1: Browse swim recovery workouts
workouts = await get_triathlon_workout_files("Swim", "recovery", "Meters")

# Step 2: Pick one from the results, e.g., "SRe1_Recovery_.json"
readable_workout = await parse_triathlon_workout_to_readable_format("Swim", "Meters", "SRe1_Recovery_.json")
```

### "Show me bike power aerobic intervals"
```python
# Step 1: Find aerobic bike workouts
workouts = await get_triathlon_workout_files("Bike", "aerobic", "Power")

# Step 2: Get readable format of an interesting one, e.g., "CAe11_Aerobic_Intervals_.json"
workout_details = await parse_triathlon_workout_to_readable_format("Bike", "Power", "CAe11_Aerobic_Intervals_.json")
```

### "I need a running tempo workout"
```python
# Step 1: Browse running tempo workouts
workouts = await get_triathlon_workout_files("Run", "tempo", "Pace")

# Step 2: Get the readable workout format
workout_data = await parse_triathlon_workout_to_readable_format("Run", "Pace", "RT1_Tempo_Run_.json")
```

## Error Handling

- **Invalid category**: You'll get "Invalid category" with valid options
- **Invalid metric**: You'll get "Invalid metric" with valid options  
- **Invalid sub-category**: You'll get available sub-categories for that sport
- **File not found**: You'll get "Workout file not found" message
- **Empty filename**: You'll get "filename parameter is required"

## Tips for Claude

1. **Always start with browsing** - Use `get_triathlon_workout_files` first to see what's available
2. **Use readable format first** - Use `parse_triathlon_workout_to_readable_format` for user-friendly display
3. **Use exact filenames** - Copy the filename exactly from the browse results
4. **Check error messages** - They contain helpful information about what's available
5. **Sport-specific filtering** - Remember each sport has different sub-categories
6. **File extension optional** - You can use "SRe1_Recovery_" or "SRe1_Recovery_.json"
7. **Triple backticks included** - The parsed format includes proper code block formatting for readability

## Readable Format Features

The `parse_triathlon_workout_to_readable_format` tool provides:
- **Workout Name**: Cleaned up from filename
- **Workout Type**: Ride/Run/Swim  
- **Total Duration**: In HH:MM format
- **Description**: In code blocks with focus and purpose
- **Intervals**: Properly formatted with:
  - Clear interval names
  - Instructions in quotes
  - Duration in m/s/h format
  - Intensity zones (% FTP for power, % LTHR for HR, meters for swim)
  - Repeat notation for sets
  - All wrapped in triple backticks for Claude

This workflow replaces the need for Claude to access files directly at system paths and provides a clean, validated interface to the workout library.