# pytframe2

A framework for building an maintaining python toolboxes for ArcGIS Pro

Meant to help split up a toolbox into tool files, toolbox files that import tools
and helper modules

## Getting Started

Setup is as simple as opening a terminal in the directory you want your tools to be and running

```sh
    git clone https://github.com/hwelch-fle/pytframe2.git
```

To immediately test out the included tools and toolboxes, you can navigate to:

```tree
    toolboxes/
    └── production_toolbox/
        └── ProductionTools.pyt
```

and add the `ProductionTools` toolbox file to your project

### Advanced Start

To start writing your own tools, you can copy one of the example tools or start a fresh file in one of the tool modules. The only requirement for a tool file is that the filename matches the tool class name.

e.g. `MyTool.py` ->

```python
import arcpy
from utils.tool import Tool

class MyTool(Tool):
    ...
```

The import functionality in the `.pyt` toolbox is as follows:

```python
def get_module(module_name: str) -> type[Tool]:
    *_, tool = module_name.rsplit(".", 1)
    return getattr(reload(import_module(module_name)), tool)

def import_tools(tool_dict: dict[str, list[str]], tool_module_name: str = "tools") -> list[type[Tool]]:
    return \
        [
            get_module(f'{tool_module_name}.{tool_sub_module}.{tool}')
            for tool_sub_module, tools in tool_dict.items()
            for tool in tools
        ]
```

- `tool_module_name` is the highest oganizational level for your tools by (default: `tools`)

- `tool_sub_module` is the second organizational level (default: `development`, `prduction`, `testing`, `utilities`)

- `tool` is the filename for the tool.

To simplify importing, the filename is used as a way to tell which class within a tool file is the actual tool
This helps prevent namespace pollution by enforcing unique names in modules through file system limitations and avoiding * imports. This means you can put anything you want into a toolfile and only the tool itself will have access to it. The namespace of the Toolbox it's imported into remains clean.

## Additional Info

Within this framework there are a number of helper modules, namely `archelp` and `models` with the `tool` and `reloader` modules containing code for pyt reload logic and dynamic toolbox building and an `ABC` for creating tools.

### tool

`Tool(ABC)` in `tool` can be extended if you have internal "tool types" that all have the same interface or messaging logic. For example:

```python
class BoolTool(Tool):
    def getParameterInfo(self) -> list[arcpy.Parameter]:
        bool_param = arcpy.Parameter(
            name = 'bool_param',
            displayName = 'Checkbox',
            ...
        )
```

Now your tools can inherit the `BoolTool` subclass to get access to that default parameter for free

### archelp

The archelp module is primarily for centralizing all functions and classes that have general usage across all or many tools. As you can see, it currently holds the `Parameters` class that allows for parameter objects to be referenced by name instead of index (a much needed change with complicated parameter configurations)

### models

The models module is an API for basic operations that you may want to do with standard Arc objects. The most developed interface in that module currently is `Table` wich allows for standard table operations to be done using builtin python methods and syntax (see the `GDBMerger` tool for examples)

## Contributing

Contributions for now will be handled through standard PRs. If you want to help develop this framework
I will be glad to explain and prioritize development and documentation in areas that people are interested in

## Authors

- **Hayden Welch**

## License

This project is licensed under the [The MIT License](LICENSE) - see the [LICENSE.md](LICENSE.md) file for
details
