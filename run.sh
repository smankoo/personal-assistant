#!/bin/bash
#
# run.sh
#
# This script performs the following steps (unless in raw or list mode):
#  1. Activates the virtual environment.
#  2. Runs the active plugins (via personal_assistant/main.py) which writes context
#     to personal_assistant/.plugins_output/0_all.output.txt.
#  3. Compiles the final prompt by invoking compile_prompt.py with the desired
#     personality (from personalities.yml) and mode (ask or direct). The compiled
#     prompt is saved to a file in the plugins output directory.
#  4. Copies the contents of that file (the compiled prompt) to the clipboard.
#  5. Deactivates the virtual environment.
#
# Special modes:
#   --raw | -r : Instead of compiling a prompt, copy only the raw plugin context.
#   --list | -l: List available personalities (case-insensitive) in a pretty table and exit.
#
# Usage:
#   ./run.sh [--personality|-p <personality>] [--mode ask|direct]
#           [--personalities_file <file>] [--context_file <file>]
#           [--template_file <file>] [--raw|-r] [--list|-l]
#
# --- Set default values ---
PERSONALITY="Sheela"
MODE="ask"
PERSONALITIES_FILE="personal_assistant/personalities.yml"
CONTEXT_FILE="personal_assistant/.plugins_output/0_all.output.txt"
TEMPLATE_FILE=""
RAW_MODE=false
LIST_MODE=false

# --- Parse command-line arguments ---
while [[ $# -gt 0 ]]; do
  key="$1"
  case $key in
    --personality|-p)
      shift
      PERSONALITY="$1"
      ;;
    --mode)
      shift
      MODE="$1"
      ;;
    --personalities_file)
      shift
      PERSONNALITIES_FILE="$1"
      PERSONALITIES_FILE="$1"  # Ensure correct variable name
      ;;
    --context_file)
      shift
      CONTEXT_FILE="$1"
      ;;
    --template_file)
      shift
      TEMPLATE_FILE="$1"
      ;;
    --raw|-r)
      RAW_MODE=true
      ;;
    --list|-l)
      LIST_MODE=true
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: $0 [--personality <personality>] [--mode ask|direct] [--personalities_file <file>]"
      echo "          [--context_file <file>] [--template_file <file>] [--raw|-r] [--list|-l]"
      exit 1
      ;;
  esac
  shift
done

# --- Check that the personalities file exists ---
if [ ! -f "$PERSONALITIES_FILE" ]; then
  echo "[ERROR] Personalities file not found: $PERSONALITIES_FILE"
  exit 1
fi

# --- Check that the virtual environment exists and activate it ---
VENV_DIR=".venv"
if [ ! -d "$VENV_DIR" ]; then
  echo "[ERROR] Virtual environment not found at $VENV_DIR"
  exit 1
fi

# Activate the virtual environment
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# --- List Mode: Display available personalities in a pretty table and exit ---
if [ "$LIST_MODE" = true ]; then
  echo "[INFO] Available Personalities:"
  python3 personality_helper.py list --file "$PERSONALITIES_FILE"
  deactivate
  exit 0
fi

# --- Check that the specified personality exists (case-insensitive) ---
python3 personality_helper.py check --personality "$PERSONALITY" --file "$PERSONALITIES_FILE"
if [ $? -ne 0 ]; then
  echo "[ERROR] Please check the personality name and try again."
  deactivate
  exit 1
fi

# --- Pre-checks for required files ---
if [ ! -f "compile_prompt.py" ]; then
  echo "[ERROR] compile_prompt.py not found in the current directory."
  deactivate
  exit 1
fi

if [ ! -f "personal_assistant/main.py" ]; then
  echo "[ERROR] personal_assistant/main.py not found."
  deactivate
  exit 1
fi

if [ -n "$TEMPLATE_FILE" ] && [ ! -f "$TEMPLATE_FILE" ]; then
  echo "[ERROR] Specified template file not found: $TEMPLATE_FILE"
  deactivate
  exit 1
fi

# --- Run plugins to generate context ---
echo "[INFO] Running plugins..."
python3 personal_assistant/main.py
if [ $? -ne 0 ]; then
  echo "[ERROR] Running plugins failed."
  deactivate
  exit 1
fi

if [ ! -f "$CONTEXT_FILE" ]; then
  echo "[ERROR] Expected context file not found: $CONTEXT_FILE"
  deactivate
  exit 1
fi

# --- If raw mode is enabled, skip prompt compilation and copy raw context ---
if [ "$RAW_MODE" = true ]; then
  echo "[INFO] Raw mode enabled. Copying raw plugin context to clipboard..."
  RAW_CONTEXT=$(cat "$CONTEXT_FILE")
  if [ -z "$RAW_CONTEXT" ]; then
    echo "[ERROR] Raw context is empty."
    deactivate
    exit 1
  fi
  if command -v pbcopy &> /dev/null; then
    echo "$RAW_CONTEXT" | pbcopy
    echo "[INFO] Raw context copied to clipboard using pbcopy."
  elif command -v xclip &> /dev/null; then
    echo "$RAW_CONTEXT" | xclip -selection clipboard
    echo "[INFO] Raw context copied to clipboard using xclip."
  elif command -v clip &> /dev/null; then
    echo "$RAW_CONTEXT" | clip
    echo "[INFO] Raw context copied to clipboard using clip."
  else
    echo "[WARNING] No clipboard command found. Please install pbcopy, xclip, or clip."
  fi
  deactivate
  exit 0
fi

# --- Define where to save the compiled prompt ---
OUTPUT_FILE="personal_assistant/.plugins_output/compiled_prompt.txt"

# --- Compile the prompt ---
echo "[INFO] Compiling prompt..."
CMD_ARGS=( "--personality" "$PERSONALITY" "--mode" "$MODE" "--personalities_file" "$PERSONALITIES_FILE" "--context_file" "$CONTEXT_FILE" "--output" "$OUTPUT_FILE" )
if [ -n "$TEMPLATE_FILE" ]; then
  CMD_ARGS+=( "--template_file" "$TEMPLATE_FILE" )
fi

python3 compile_prompt.py "${CMD_ARGS[@]}"
if [ $? -ne 0 ]; then
  echo "[ERROR] Failed to compile prompt."
  deactivate
  exit 1
fi

if [ ! -f "$OUTPUT_FILE" ]; then
  echo "[ERROR] Compiled prompt file not found: $OUTPUT_FILE"
  deactivate
  exit 1
fi

echo "[INFO] Prompt compiled successfully and saved to $OUTPUT_FILE."

# --- Copy the compiled prompt to the clipboard ---
COMPILED_PROMPT=$(cat "$OUTPUT_FILE")
if [ -z "$COMPILED_PROMPT" ]; then
  echo "[ERROR] Compiled prompt is empty."
  deactivate
  exit 1
fi

echo "[INFO] Copying compiled prompt to clipboard..."
if command -v pbcopy &> /dev/null; then
  echo "$COMPILED_PROMPT" | pbcopy
  echo "[INFO] Compiled prompt copied to clipboard using pbcopy."
elif command -v xclip &> /dev/null; then
  echo "$COMPILED_PROMPT" | xclip -selection clipboard
  echo "[INFO] Compiled prompt copied to clipboard using xclip."
elif command -v clip &> /dev/null; then
  echo "$COMPILED_PROMPT" | clip
  echo "[INFO] Compiled prompt copied to clipboard using clip."
else
  echo "[WARNING] No clipboard command found. Please install pbcopy, xclip, or clip."
fi

# --- Deactivate the virtual environment ---
deactivate

echo "[INFO] Process completed."