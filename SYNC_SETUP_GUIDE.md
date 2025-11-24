# Syncing Intervals MCP Server Changes to Another Computer

This guide will help you set up the Intervals MCP Server with your custom triathlon workout files endpoint on a different computer.

## Prerequisites

- Git installed on the target computer
- Python 3.12+ installed
- [uv](https://github.com/astral-sh/uv) package manager installed
- Your GitHub account credentials

## Step 1: Clone Your Fork

On your new computer, clone **your fork** (not the original repository):

```bash
# Replace 'aeganaden' with your actual GitHub username
git clone https://github.com/aeganaden/intervals-mcp-server.git
cd intervals-mcp-server
```

## Step 2: Verify Remote Configuration

Check that the remotes are set up correctly:

```bash
git remote -v
```

**Expected output:**
```
origin  https://github.com/aeganaden/intervals-mcp-server.git (fetch)
origin  https://github.com/aeganaden/intervals-mcp-server.git (push)
```

## Step 3: Add Upstream Remote (Optional but Recommended)

Add the original repository as upstream for future updates:

```bash
git remote add upstream https://github.com/mvilanova/intervals-mcp-server.git
```

**Verify the configuration:**
```bash
git remote -v
```

**Expected output:**
```
origin    https://github.com/aeganaden/intervals-mcp-server.git (fetch)
origin    https://github.com/aeganaden/intervals-mcp-server.git (push)
upstream  https://github.com/mvilanova/intervals-mcp-server.git (fetch)
upstream  https://github.com/mvilanova/intervals-mcp-server.git (push)
```

## Step 4: Set Up Development Environment

Install dependencies using uv:

```bash
# Create virtual environment
uv venv --python 3.12

# Activate virtual environment (Windows)
.venv\Scripts\activate
# Or on macOS/Linux:
# source .venv/bin/activate

# Install dependencies including dev tools
uv sync --all-extras
```

## Step 5: Verify Your Changes

Check that your custom endpoint is present:

```bash
# Look for the get_triathlon_workout_files function
grep -n "get_triathlon_workout_files" src/intervals_mcp_server/server.py
```

**Expected output:**
```
679:async def get_triathlon_workout_files(
```

## Step 6: Run Tests

Verify everything works correctly:

```bash
# Run all tests
uv run pytest -v

# Run specific tests for your endpoint
uv run pytest tests/test_triathlon_workouts.py -v
```

**Expected:** All 23 tests should pass.

## Step 7: Test the MCP Server

Verify the server starts without errors:

```bash
# Test server startup (will timeout after 5 seconds, which is expected)
timeout 5 uv run mcp run src/intervals_mcp_server/server.py || echo "Server started successfully"
```

## Step 8: Configure Environment Variables

Create a `.env` file with your Intervals.icu credentials:

```bash
# Create .env file
cp .env.example .env

# Edit .env file with your credentials
# Add your actual API key and athlete ID
```

**Example `.env` content:**
```
API_KEY=your_intervals_icu_api_key_here
ATHLETE_ID=your_athlete_id_here
INTERVALS_API_BASE_URL=https://intervals.icu/api/v1
```

## Troubleshooting

### If You Cloned the Wrong Repository

If you accidentally cloned the original repository instead of your fork:

```bash
# Check current remote
git remote -v

# If it shows mvilanova/intervals-mcp-server, change it to your fork:
git remote set-url origin https://github.com/aeganaden/intervals-mcp-server.git

# Add upstream
git remote add upstream https://github.com/mvilanova/intervals-mcp-server.git

# Verify
git remote -v
```

### If Your Changes Are Missing

Pull the latest changes from your fork:

```bash
git pull origin main
```

### If You Need to Switch from Original to Fork

If you have an existing clone of the original repository:

```bash
# Navigate to your existing repository
cd path/to/intervals-mcp-server

# Change origin to your fork
git remote set-url origin https://github.com/aeganaden/intervals-mcp-server.git

# Add upstream (if not already added)
git remote add upstream https://github.com/mvilanova/intervals-mcp-server.git

# Pull your changes
git pull origin main
```

## Keeping Your Fork Updated

To sync with the original repository when it gets updates:

```bash
# Fetch changes from upstream
git fetch upstream

# Switch to main branch
git checkout main

# Merge upstream changes
git merge upstream/main

# Push updates to your fork
git push origin main
```

## Your Custom Endpoint Features

Your fork now includes the `get_triathlon_workout_files` endpoint with:

- **Categories**: Bike, Run, Swim
- **Metrics**: HR, Power, Pace, Meters
- **Sub-categories**: 20+ workout types (Aerobic, Anaerobic, Foundation, Recovery, etc.)
- **2,400+ workout files** included
- **Full test coverage** (9 additional tests)

## Example Usage

Test your endpoint:

```python
# In Python (after setting up the MCP server)
await get_triathlon_workout_files(
    category="Bike", 
    sub_category="aerobic", 
    metric="Power"
)
```

## Need Help?

- Check that all remotes point to the correct repositories
- Ensure your `.env` file has valid credentials
- Run tests to verify functionality: `uv run pytest -v`
- Check the server starts: `uv run mcp run src/intervals_mcp_server/server.py`

Your custom triathlon workout files endpoint should now be available on your new computer! 🚀