import importlib
import os

from oxygent.oxy import FunctionHub

# List of tool modules to import
tool_modules = [
    "math_tools",
    "file_tools",
    "time_tools",
    "http_tools",
    "string_tools",
    "system_tools",
    "shell_tools",
    "python_tools",
    "baidu_search_tools",
    "image_gen_tools",
]

__all__ = []

# Get the current package directory path
package_dir = os.path.dirname(__file__)

for module_name in tool_modules:
    module_path = os.path.join(package_dir, f"{module_name}.py")

    # First check if the module file exists
    if not os.path.exists(module_path):
        print(
            f"Warning: Failed to import tool '{module_name}': Module file does not exist, please check '{module_path}'"
        )
        globals()[module_name] = None
        continue

    try:
        # Dynamically import the module
        module = importlib.import_module(f".{module_name}", __package__)

        # Filter out all non-private attributes that are instances of FunctionHub
        function_hub_instances = [
            attr
            for attr in dir(module)
            if not attr.startswith("_")  # Exclude private attributes
            and isinstance(
                getattr(module, attr), FunctionHub
            )  # Only keep FunctionHub instances
        ]

        if function_hub_instances:
            # Add eligible instances to the current scope and __all__
            for attr_name in function_hub_instances:
                attr_value = getattr(module, attr_name)
                globals()[attr_name] = attr_value
                __all__.append(attr_name)
        else:
            print(f"Warning: No FunctionHub instances found in module '{module_name}'")

    except ImportError as e:
        # Catch import errors and extract the missing package name
        error_msg = str(e)
        missing_package = None

        if "No module named" in error_msg:
            parts = error_msg.split("'")
            if len(parts) >= 2:
                missing_package = parts[-2]

        # Print a clear prompt message
        if missing_package and not missing_package.startswith(__package__):
            print(
                f"Warning: Failed to import tool '{module_name}': Missing dependency package '{missing_package}', please run: pip install {missing_package}"
            )
        else:
            print(f"Warning: Failed to import tool '{module_name}': {error_msg}")

        # Set the module entry to None to prevent errors in subsequent use
        globals()[module_name] = None
