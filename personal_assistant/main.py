#!/usr/bin/env python3
"""
Main script for the Personal Assistant.
Loads and executes plugins in the order specified in plugin_config.yml.
"""

import os
import sys
import yaml
import importlib.util
from datetime import datetime

# Define paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.join(BASE_DIR, "plugins")
# Assume the config lives in a dedicated config directory at the repo root:
PLUGIN_CONFIG_FILE = os.path.join(os.path.dirname(BASE_DIR), "plugin_config.yml")
PLUGIN_OUTPUT_DIR = os.path.join(BASE_DIR, ".plugins_output")
FULL_CONTEXT_FILE_PATH = os.path.join(PLUGIN_OUTPUT_DIR, "0_all.output.txt")


def load_active_plugins():
    """
    Load plugins in the order specified by the active_plugins list in the config file.
    """
    if not os.path.exists(PLUGIN_CONFIG_FILE):
        raise FileNotFoundError(
            f"Plugin config file not found at: {PLUGIN_CONFIG_FILE}"
        )

    with open(PLUGIN_CONFIG_FILE, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    active_plugin_names = config.get("active_plugins", [])
    plugins = []
    for plugin_name in active_plugin_names:
        plugin_file = f"{plugin_name}.py"
        plugin_path = os.path.join(PLUGIN_DIR, plugin_file)
        if not os.path.exists(plugin_path):
            print(
                f"[WARNING] Plugin file for '{plugin_name}' not found at {plugin_path}. Skipping."
            )
            continue

        spec = importlib.util.spec_from_file_location(plugin_name, plugin_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[plugin_name] = module
        spec.loader.exec_module(module)
        plugins.append(module)
        print(f"[INFO] Loaded plugin: {plugin_name}")
    return plugins, active_plugin_names


def main():
    # Load active plugins based on configuration (preserving order)
    print("[INFO] Loading active plugins...")
    plugins, active_plugin_names = load_active_plugins()

    # Ensure the plugin output directory exists and clear any previous output
    if not os.path.exists(PLUGIN_OUTPUT_DIR):
        os.makedirs(PLUGIN_OUTPUT_DIR)
    else:
        for filename in os.listdir(PLUGIN_OUTPUT_DIR):
            file_path = os.path.join(PLUGIN_OUTPUT_DIR, filename)
            if os.path.isfile(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                os.rmdir(file_path)

    # Run each plugin in order
    for plugin in plugins:
        if hasattr(plugin, "get_output"):
            plugin_start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            plugin_name = plugin.__name__
            print(f"> Running plugin: {plugin_name}...")
            try:
                output_data = (
                    plugin.get_output()
                )  # Expecting a dict with an "output" key
                plugin_output = f"[[ {plugin_name} ]]\n{output_data.get('output', '')}"
                # Save each plugin's output to a file named after the plugin
                output_file = os.path.join(
                    PLUGIN_OUTPUT_DIR, f"{plugin_name}.output.txt"
                )
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(plugin_output)
            except Exception as e:
                print(f"[ERROR] Plugin {plugin_name} failed: {e}")
            finally:
                plugin_end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                plugin_total_run_time = (
                    datetime.strptime(plugin_end_time, "%Y-%m-%d %H:%M:%S")
                    - datetime.strptime(plugin_start_time, "%Y-%m-%d %H:%M:%S")
                ).total_seconds()
                # convert to human readable time
                plugin_total_run_time_human_readable = (
                    f"{plugin_total_run_time:.2f} seconds"
                    if plugin_total_run_time < 60
                    else f"{plugin_total_run_time/60:.2f} minutes"
                )
                print(
                    f"[INFO] Plugin {plugin_name} completed. Total run time: {plugin_total_run_time_human_readable}"
                )
                print(
                    f"[INFO] Output saved to {os.path.join(PLUGIN_OUTPUT_DIR, f'{plugin_name}.output.txt')}"
                )

        else:
            print(
                f"[WARNING] Plugin {plugin.__name__} does not implement get_output(). Skipping."
            )

    # Combine plugin outputs in the order specified in the YAML config
    with open(FULL_CONTEXT_FILE_PATH, "w", encoding="utf-8") as final_context:
        for plugin_name in active_plugin_names:
            output_file = os.path.join(PLUGIN_OUTPUT_DIR, f"{plugin_name}.output.txt")
            if os.path.exists(output_file):
                with open(output_file, "r", encoding="utf-8") as f:
                    final_context.write(f.read() + "\n\n")
            else:
                print(
                    f"[DEBUG] No output file for plugin '{plugin_name}' (it might have been skipped)."
                )

    print(
        f"[INFO] All active plugins have been run. Final context saved to {FULL_CONTEXT_FILE_PATH}"
    )


if __name__ == "__main__":
    main()
