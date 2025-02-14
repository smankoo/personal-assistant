#!/bin/bash

# Check if the current directory is a git repository
if [ ! -d .git ]; then
  echo "This script must be run from the root of a git repository."
  exit 1
fi

# Get the list of files tracked by git, excluding those in .gitignore
files=$(git ls-files)

# Create a reST string with file paths and contents
rst_output=""
for file in $files; do
  if [ -f "$file" ]; then
    rst_output+="\n$file\n"
    rst_output+="$(printf '=%0.s' $(seq 1 ${#file}))\n\n"
    rst_output+=".. code-block:: none\n\n"
    while IFS= read -r line; do
      rst_output+="    $line\n"
    done < "$file"
    rst_output+="\n"
  fi
done

# Copy to clipboard
echo -e "$rst_output" | pbcopy

echo "Copied to clipboard in reStructuredText format."
