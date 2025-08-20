import sys
from importlib import reload
from pathlib import Path

# Manually add the path to the root of the project
ROOT = str(Path(__file__).parents[2].absolute())

# Insert the module roots to the system path
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)  # ../pytframe2
if rf"{ROOT}\tools" not in sys.path:
    sys.path.insert(1, rf"{ROOT}\tools")  # ../pytframe2/tools
if rf"{ROOT}\utils" not in sys.path:
    sys.path.insert(2, rf"{ROOT}\utils")  # ../pytframe2/utils

# NOTE: Add more module paths here if needed

import utils.archelp as pyt_reload_archelp
import utils.models as pyt_reload_models

# Import dynamic modules with pyt_reload prefix
import utils.reloader as pyt_reload_reloader
import utils.tool as pyt_reload_tool

# import utils.models as pyt_reload_models

# Inline reloader of dynamic modules
[
    print(f"Reloaded {reload(module).__name__}")
    for module_name, module in globals().items()
    if module_name.startswith("pyt_reload")
]

# Import the Tool Importer function
from utils.reloader import import_tools
from utils.tool import Tool

## TODO: Move this to a configuration file
TOOLS = {
    "development": [
        "DevTool",
    ],
    "utilities": [
        "VersionControl",
    ],
    "production": [
        "VertexBuffer",
        "GDBMerger",
    ],
    "processing": [
        "A5SurveyProcessor",
    ],
}

# class Toolbox(object):
#     def __init__(self):
#         """Define the toolbox (the name of the toolbox is the name of the .pyt file)."""
#         self.label = "Survey Data Processing Toolbox"
#         self.alias = "surveyprocessing"
#         self.tools = [SurveyDataProcessor]

IMPORTS: list[type[Tool]] = import_tools(TOOLS)

# Manually add the tools to the global namespace
globals().update({tool.__name__: tool for tool in IMPORTS})


class Toolbox(object):
    def __init__(self):
        """Define the toolbox (the name of the toolbox is the name of the
        .pyt file)."""

        self.label = "Processing Toolbox"
        self.alias = self.label.replace(" ", "")

        # List of tool classes associated with this toolbox
        self.tools: list[type[Tool]] = IMPORTS
