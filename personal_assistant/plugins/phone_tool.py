#!/usr/bin/env python3
"""
Plugin: Phone Tool (Org & Employee Info)
This plugin retrieves employee and organizational data from phonetool.amazon.com,
including organizational chain, peers, and direct reports for specified aliases.
It uses curl (via subprocess) to request JSON data from the Phone Tool API.
The output is compiled into several sections:
  - Org Chain
  - Peers
  - Direct Reports
  - Andrea's Reports
  - Andrea's Org Chain

Caching is implemented for 7 days (604800 seconds) to avoid repeated API calls.
"""

import requests
import argparse
import subprocess
import json
import os
import time

# Domain & output constants
DOMAIN = 'https://phonetool.amazon.com'
# (No file writing is performed in this plugin version; output is returned via get_output())

# ----------------------------
# API Request Functions
# ----------------------------

def execute_request(url):
    """
    Executes a curl command to fetch JSON data from the provided URL.
    Returns the parsed JSON content or None if parsing fails.
    """
    cmd = (
        "curl '{0}' --anyauth --location-trusted -u: -c /tmp/cookies.txt "
        "-b /tmp/cookies.txt -L --cookie ~/.midway/cookie --cookie-jar ~/.midway/cookie "
        "-s -H 'Content-Type: application/json;' -H 'Accept: application/json'"
    ).format(url)

    process = subprocess.Popen(
        cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True
    )
    stdout, stderr = process.communicate()
    try:
        content = json.loads(stdout)
        return content
    except Exception as err:
        print('Unable to parse json: {0}'.format(err))
        return None

def get_employee_info(login):
    """
    Retrieves employee information as JSON from Phone Tool for a given login.
    """
    url = '{0}/users/{1}.json'.format(DOMAIN, login)
    return execute_request(url=url)

def get_manager_alias(alias, levels_above=1):
    """
    Recursively retrieves the manager alias, going up a number of levels as specified.
    """
    employee_info = get_employee_info(alias)
    if not employee_info or 'manager' not in employee_info:
        return None

    manager_alias = employee_info['manager']['login']
    if levels_above == 1:
        return manager_alias
    return get_manager_alias(manager_alias, levels_above - 1)

# ----------------------------
# Output Formatting Functions
# ----------------------------

def get_employee_string(alias, details=True):
    """
    Returns a formatted string for an employee.
    If details is True, appends the full employee info.
    """
    employee_info = get_employee_info(alias)
    if employee_info.get('status') == "error":
        print(f"\033[91mError: {employee_info['message']}, {employee_info['desc']}\033[0m")
        exit(1)
    name = employee_info.get('name', 'Unknown')
    if details:
        return f"{name} ({alias}) {employee_info}"
    return f"{name} ({alias})"

def print_reports(alias, level=1):
    """
    Recursively builds a string of direct reports for the given alias.
    Each level is indented accordingly.
    """
    reports_string = ""
    employee_info = get_employee_info(alias)
    if not employee_info or 'direct_reports' not in employee_info or not employee_info['direct_reports']:
        return None

    direct_reports = employee_info['direct_reports']
    direct_reports_aliases = [report['login'] for report in direct_reports]

    # For level 1, include the manager's own info at the top
    if level == 1:
        employee_string = get_employee_string(alias)
        reports_string += employee_string

    for direct_report_alias in direct_reports_aliases:
        employee_string = get_employee_string(direct_report_alias)
        reports_string += f"\n{'    ' * level}|- {employee_string}"
        # Optionally, you can print a progress dot:
        print(".", end="", flush=True)
        sub_reports_string = print_reports(direct_report_alias, level + 1)
        if sub_reports_string:
            reports_string += sub_reports_string
    return reports_string

def print_org_chain(alias, org_chain=None, indent=0):
    """
    Builds a string representing the organizational chain from the top down
    for the given alias.
    """
    if org_chain is None:
        org_chain = []
    manager_alias = alias
    while manager_alias is not None:
        employee_string = get_employee_string(manager_alias)
        org_chain.append(employee_string)
        manager_alias = get_manager_alias(manager_alias)
    org_chain.reverse()

    org_chain_string = ""
    current_indent = indent
    for i, name in enumerate(org_chain):
        if i == 0:
            org_chain_string += name
        else:
            current_indent += 3
            org_chain_string += f"\n{' ' * current_indent}|- {name}"
    return org_chain_string

def print_peers(alias, degrees=1):
    """
    Retrieves and returns the peers of the given employee.
    Peers are defined as the direct reports of the manager found
    a specified number of levels above the given alias.
    """
    manager_alias = get_manager_alias(alias, levels_above=degrees)
    if manager_alias is None:
        return None
    return print_reports(manager_alias)

# ----------------------------
# Plugin Main Compilation Function
# ----------------------------

# Import the caching decorator from the project tools
from personal_assistant.tools.caching import cached_output

# Cache output for 7 days (604800 seconds)
@cached_output(max_age_seconds=604800)
def compile_phonetool_output():
    """
    Compiles the organizational information:
      - Org Chain of 'smankoo'
      - Peers of 'smankoo' (2 levels above)
      - Direct Reports of 'smankoo'
      - Direct Reports and Org Chain for 'andrebap' (Andrea Baptiste)
    Returns the combined output as a formatted string.
    """
    org_chain_string = print_org_chain('smankoo')
    peers_string = print_peers('smankoo', degrees=2)
    reports_string = print_reports('smankoo')
    if reports_string is None:
        reports_string = "No direct reports"
    andrea_org = print_reports('andrebap')
    andrea_org_chain = print_org_chain('andrebap')

    output_lines = []
    output_lines.append("[[ Org Chain ]]")
    output_lines.append(org_chain_string)
    output_lines.append("\n[[ Peers ]]")
    output_lines.append(peers_string if peers_string else "No peers found")
    output_lines.append("\n[[ Direct Reports ]]")
    output_lines.append(reports_string)
    output_lines.append("\n[[ Andrea's Reports ]]")
    output_lines.append(andrea_org if andrea_org else "No reports found")
    output_lines.append("\n[[ Andrea's Org Chain ]]")
    output_lines.append(andrea_org_chain)
    return "\n".join(output_lines)

# ----------------------------
# Plugin Entry Point
# ----------------------------

def get_output():
    """
    Plugin entry point.
    Returns a dictionary with the plugin name and the compiled organizational info.
    """
    try:
        output = compile_phonetool_output()
    except Exception as e:
        output = f"Error fetching Phone Tool data: {e}"
    return {"plugin_name": "phone_tool", "output": output}

if __name__ == '__main__':
    # For standalone testing
    result = get_output()
    print(result["output"])
