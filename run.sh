#!/bin/bash
#
# run.sh
#
# This script performs the following steps:
#   1. Activates the virtual environment.
#   2. Runs active plugins (via personal_assistant/main.py) to generate context.
#   3. Compiles the final prompt using compile_prompt.py.
#   4. If the --ai flag is provided, the compiled prompt is sent to the selected LLM provider
#      (using our new llm client interface, e.g. openai or awsbedrock). Otherwise, the compiled
#      prompt is copied to the clipboard.
#   5. Deactivates the virtual environment.
#
# Usage:
#   ./run.sh [--help|-h] [--personality <name>] [--mode ask|direct] [--personalities_file <file>]
#            [--context_file <file>] [--template_file <file>] [--raw|-r] [--list|-l] [--ai <provider>]

# Default values
PERSONALITY="Sheela"
MODE="ask"
PERSONALITIES_FILE="personal_assistant/personalities.yml"
CONTEXT_FILE="personal_assistant/.plugins_output/0_all.output.txt"
TEMPLATE_FILE=""
RAW_MODE=false
LIST_MODE=false
LLM_PROVIDER=""  # If provided (e.g. "openai" or "awsbedrock"), the prompt will be sent to that provider

# Parse command-line arguments
while [[ $# -gt 0 ]]; do
  key="$1"
  case $key in
    --help|-h)
      echo "Usage: $0 [--help|-h] [--personality <name>] [--mode ask|direct] [--personalities_file <file>]"
      echo "          [--context_file <file>] [--template_file <file>] [--raw|-r] [--list|-l] [--ai <provider>]"
      echo ""
      echo "Options:"
      echo "  --help, -h                Show this help message and exit."
      echo "  --personality, -p <name>    Specify personality. Default: ${PERSONALITY}"
      echo "  --mode <ask|direct>        Set mode. Default: ${MODE}"
      echo "  --personalities_file <file> Specify personalities file. Default: ${PERSONALITIES_FILE}"
      echo "  --context_file <file>      Specify context file. Default: ${CONTEXT_FILE}"
      echo "  --template_file <file>     Specify template file (optional)."
      echo "  --raw, -r                Enable raw mode."
      echo "  --list, -l               Enable list mode."
      echo "  --ai <provider>          Specify LLM provider (e.g., openai or awsbedrock)."
      exit 0
      ;;
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
      PERSONALITIES_FILE="$1"
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
    --ai)
      shift
      LLM_PROVIDER="$1"
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: $0 [--personality <name>] [--mode ask|direct] [--personalities_file <file>]"
      echo "          [--context_file <file>] [--template_file <file>] [--raw|-r] [--list|-l] [--ai <provider>]"
      exit 1
      ;;
  esac
  shift
done

# Ensure the personalities file exists.
if [ ! -f "$PERSONALITIES_FILE" ]; then
  echo "[ERROR] Personalities file not found: $PERSONALITIES_FILE"
  exit 1
fi

# Activate the virtual environment.
VENV_DIR=".venv"
if [ ! -d "$VENV_DIR" ]; then
  echo "[ERROR] Virtual environment not found at $VENV_DIR"
  exit 1
fi
source "$VENV_DIR/bin/activate"

# List mode: display available personalities and exit.
if [ "$LIST_MODE" = true ]; then
  echo "[INFO] Available Personalities:"
  python3 personality_helper.py list --file "$PERSONALITIES_FILE"
  deactivate
  exit 0
fi

# Check that the specified personality exists.
python3 personality_helper.py check --personality "$PERSONALITY" --file "$PERSONALITIES_FILE"
if [ $? -ne 0 ]; then
  echo "[ERROR] Please check the personality name and try again."
  deactivate
  exit 1
fi

# Pre-check for required files.
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

# Run plugins to generate context.
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

# If raw mode is enabled, copy raw plugin context to clipboard and exit.
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

# run AI Observations
echo "[INFO] Running AI Observations..."
python3 ai_observer.py "$CONTEXT_FILE"

# Define where to save the compiled prompt.
OUTPUT_FILE="personal_assistant/.plugins_output/compiled_prompt.txt"

# Compile the prompt.
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

# If AI mode is enabled, send the compiled prompt to the selected LLM provider.
if [ -n "$LLM_PROVIDER" ]; then
  echo "[INFO] Sending compiled prompt to ${LLM_PROVIDER}..."
  # Call llm_client_runner.py with the compiled prompt file and provider name.
  python3 llm_runner.py "$OUTPUT_FILE" "$LLM_PROVIDER"
  deactivate
  exit 0
fi

# Default: copy the compiled prompt to the clipboard.
echo "[INFO] Copying compiled prompt to clipboard..."
COMPILED_PROMPT=$(cat "$OUTPUT_FILE")
if [ -z "$COMPILED_PROMPT" ]; then
  echo "[ERROR] Compiled prompt is empty."
  deactivate
  exit 1
fi

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

# Deactivate the virtual environment.
deactivate