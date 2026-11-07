import sys
from pathlib import Path

here = Path(__file__).resolve().parent
# The shared home_screen package: the nearest one in a parent directory
sys.path.insert(0, str(next(p for p in here.parents if (p / "home_screen" / "__init__.py").is_file())))
from home_screen.home import location_home  # noqa: E402

intelclass = location_home(here / "floorplan.yaml")
