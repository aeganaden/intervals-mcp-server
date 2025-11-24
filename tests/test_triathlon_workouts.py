"""Test for the triathlon workout files endpoint."""

import os
import pytest
from intervals_mcp_server.server import get_triathlon_workout_files


class TestTriathlonWorkoutFiles:
    """Test class for triathlon workout files endpoint."""

    @pytest.mark.asyncio
    async def test_valid_bike_hr(self):
        """Test getting Bike workouts with HR metric."""
        result = await get_triathlon_workout_files(category="Bike", metric="HR")
        assert "Found" in result
        assert "Bike (HR metric)" in result
        assert "📋 **" in result  # Check for formatted file entries

    @pytest.mark.asyncio
    async def test_valid_bike_power(self):
        """Test getting Bike workouts with Power metric."""
        result = await get_triathlon_workout_files(category="Bike", metric="Power")
        assert "Found" in result
        assert "Bike (Power metric)" in result
        assert "📋 **" in result

    @pytest.mark.asyncio
    async def test_valid_run_hr(self):
        """Test getting Run workouts with HR metric."""
        result = await get_triathlon_workout_files(category="Run", metric="HR")
        assert "Found" in result
        assert "Run (HR metric)" in result
        assert "📋 **" in result

    @pytest.mark.asyncio
    async def test_with_subcategory_filter(self):
        """Test filtering by sub-category."""
        result = await get_triathlon_workout_files(
            category="Bike", 
            sub_category="aerobic", 
            metric="HR"
        )
        assert "Found" in result
        assert "aerobic" in result
        # Should return fewer files than without filter
        assert len(result) < 15000  # Rough check

    @pytest.mark.asyncio
    async def test_invalid_category(self):
        """Test invalid category returns error."""
        result = await get_triathlon_workout_files(category="Invalid", metric="HR")
        assert "Error: Invalid category" in result
        assert "Bike, Run, Swim" in result

    @pytest.mark.asyncio
    async def test_invalid_metric(self):
        """Test invalid metric returns error."""
        result = await get_triathlon_workout_files(category="Bike", metric="Invalid")
        assert "Error: Invalid metric" in result
        assert "HR, Power, Pace, Meters" in result

    @pytest.mark.asyncio
    async def test_nonexistent_subcategory(self):
        """Test non-existent sub-category returns empty result."""
        result = await get_triathlon_workout_files(
            category="Bike", 
            sub_category="nonexistent_category", 
            metric="HR"
        )
        assert "No workout files found" in result
        assert "nonexistent_category" in result

    @pytest.mark.asyncio
    async def test_file_structure_check(self):
        """Test that workout files directory structure exists."""
        # Check that the expected directories exist
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        workout_base = os.path.join(base_dir, "src", "intervals_mcp_server", "triathlon_workout_files")
        
        expected_dirs = [
            "80_20_Bike_HR_80_20_Endurance_",
            "80_20_Bike_Power_80_20_Endurance_",
            "80_20_Run_HR_80_20_Endurance_",
            "80_20_Run_Pace_80_20_Endurance_",
            "80_20_Swim_Meters_80_20_Endurance_"
        ]
        
        for dir_name in expected_dirs:
            dir_path = os.path.join(workout_base, dir_name)
            assert os.path.exists(dir_path), f"Directory {dir_path} should exist"

    @pytest.mark.asyncio
    async def test_response_format(self):
        """Test that response includes expected formatting elements."""
        result = await get_triathlon_workout_files(category="Bike", metric="HR")
        
        # Check for expected formatting elements
        assert "Duration:" in result
        assert "Target:" in result  
        assert "Description:" in result
        assert "minutes" in result
        assert "📋 **" in result  # File icons

    @pytest.mark.asyncio
    async def test_get_specific_workout_file_content(self):
        """Test getting specific workout file content."""
        from intervals_mcp_server.server import get_triathlon_workout_file_content
        
        # Test valid file
        result = await get_triathlon_workout_file_content("Swim", "Meters", "SRe1_Recovery_.json")
        assert result.startswith("{")  # Should be valid JSON
        assert "Recovery" in result or "recovery" in result
        
        # Test invalid filename
        result = await get_triathlon_workout_file_content("Swim", "Meters", "NonExistent.json")
        assert "Error: Workout file 'NonExistent.json' not found" in result
        
        # Test invalid category
        result = await get_triathlon_workout_file_content("Invalid", "Meters", "SRe1_Recovery_.json")
        assert "Error: Invalid category 'Invalid'" in result
        
        # Test invalid metric
        result = await get_triathlon_workout_file_content("Swim", "Invalid", "SRe1_Recovery_.json")
        assert "Error: Invalid metric 'Invalid'" in result
        
        # Test empty filename
        result = await get_triathlon_workout_file_content("Swim", "Meters", "")
        assert "Error: filename parameter is required" in result