# Personal Assistant

The **Personal Assistant** is a modular, extensible Python application designed to aggregate contextual information from multiple sources and compile it into a structured prompt for large language model (LLM) interactions. Built around a plugin-based architecture, this assistant can be easily extended or customized to suit your needs—from fetching weather updates and calendar events to reading your Obsidian notes and emails.

---

## Features

- **Plugin Architecture:**  
  Dynamically load and execute plugins to gather context from various sources (e.g., weather, calendar, email, location, and more).  
  Customize which plugins are active via the [`plugin_config.yml`](plugin_config.yml) file.

- **Context Aggregation & Prompt Compilation:**  
  After running the plugins, the assistant compiles all outputs into a single context file. This context is then merged with a customizable prompt template (see the `prompt_templates/` directory) via [`compile_prompt.py`](compile_prompt.py).

- **Personality Profiles:**  
  Leverage predefined personality configurations (in [`personalities.yml`](personalities.yml)) to customize how the assistant interacts with you. Use the helper script [`personality_helper.py`](personality_helper.py) to list or check available personalities.

- **Clipboard Integration:**  
  Use the provided [`run.sh`](run.sh) shell script to run the entire workflow—from activating the virtual environment, running plugins, compiling the prompt, and copying the final prompt to your clipboard.

- **Caching:**  
  Many plugins use a caching mechanism (configured via [`personal_assistant/tools/caching.py`](personal_assistant/tools/caching.py)) to avoid repeated API calls and improve performance.

---

## Table of Contents

- [Personal Assistant](#personal-assistant)
  - [Features](#features)
  - [Table of Contents](#table-of-contents)
  - [Installation](#installation)
    - [Prerequisites](#prerequisites)
    - [Setup](#setup)
  - [Configuration](#configuration)
  - [Usage](#usage)
    - [Running the Assistant](#running-the-assistant)
    - [Running Individual Plugins](#running-individual-plugins)
  - [Plugins Overview](#plugins-overview)
  - [Development](#development)
    - [Folder Structure](#folder-structure)
    - [Running Tests \& Debugging](#running-tests--debugging)
  - [Contributing](#contributing)
  - [License](#license)
  - [Acknowledgements](#acknowledgements)

---

## Installation

### Prerequisites

- **Python 3.8+**
- **pip** (or another Python package manager)
- A terminal (Unix shell, Git Bash on Windows, etc.)
- (Optional) A virtual environment tool

### Setup

1. **Clone the repository:**

   ```bash
   git clone https://github.com/smankoo/personal-assistant.git
   cd personal-assistant
   ```

2. **Create and activate a virtual environment:**

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Environment Variables:**

   - Copy the example file:

     ```bash
     cp .env.example .env
     ```

   - Open `.env` and populate it with your API keys and credentials (for weather, iCloud, ProtonMail, Strava, Obsidian, etc.).

5. **(Optional) Install the package in editable mode:**

   ```bash
   pip install -e .
   ```

---

## Configuration

- **Plugin Configuration:**  
  Active plugins are defined in [`plugin_config.yml`](plugin_config.yml). To disable a plugin, remove or comment it out in this file.

- **Personalities:**  
  Customize the assistant’s behavior and tone using profiles defined in [`personalities.yml`](personalities.yml).  
  Use [`personality_helper.py`](personality_helper.py) to list available personalities or validate a chosen personality.

- **Prompt Templates:**  
  The assistant supports two prompt modes—**ask** and **direct**—with templates available in the [`prompt_templates/`](prompt_templates/) folder.  
  To override the default template, pass the template file path as an argument when running the prompt compilation.

---

## Usage

### Running the Assistant

The complete workflow is managed by the [`run.sh`](run.sh) script, which:

1. Activates the virtual environment.
2. Executes active plugins via [`personal_assistant/main.py`](personal_assistant/main.py) to generate context.
3. Compiles the final prompt using [`compile_prompt.py`](compile_prompt.py) (merging personality data, context, and the prompt template).
4. Copies the compiled prompt to your clipboard.
5. Deactivates the virtual environment.

**To run the assistant:**

```bash
./run.sh --personality "Sheela" --mode ask
```

Additional options include:

- `--raw` or `-r` to copy only the raw plugin context.
- `--list` or `-l` to list available personalities.
- `--template_file` to specify a custom prompt template.

### Running Individual Plugins

If you want to test or run a single plugin, execute its Python module directly. For example:

```bash
python3 personal_assistant/plugins/current_date.py
```

---

## Plugins Overview

The assistant currently supports (but is not limited to) the following plugins:

- **current_date:** Displays the current date and time.
- **location:** Determines your location using multiple IP-based services.
- **weather:** Fetches current weather, hourly, and daily forecasts.
- **icloud_calendar:** Retrieves upcoming events from your iCloud calendar.
- **icloud_mail:** Reads recent emails from your iCloud account.
- **proton_mail:** Retrieves emails via ProtonMail’s IMAP service.
- **strava:** Fetches recent activity data from Strava.
- **obsidian_notes:** Extracts AI-context-enabled notes from an Obsidian vault.

_Note: Additional plugins (e.g., search, static_context, todo_list) are available but may be disabled by default._

---

## Development

### Folder Structure

```
.
├── personal_assistant/            # Main application module
│   ├── __init__.py
│   ├── main.py                  # Main entry point for running plugins
│   ├── plugins/                 # Directory containing all plugins
│   │   ├── current_date.py
│   │   ├── location.py
│   │   ├── weather.py
│   │   ├── icloud_calendar.py
│   │   ├── icloud_mail.py
│   │   ├── proton_mail.py
│   │   ├── strava.py
│   │   └── ... (other plugins, some may be disabled)
│   └── tools/                   # Utility modules (e.g., caching, web_scraper)
│       ├── caching.py
│       └── web_scraper.py
├── prompt_templates/              # Prompt template files for 'ask' and 'direct' modes
├── personalities.yml            # YAML file defining personality configurations
├── plugin_config.yml            # YAML file specifying active plugins
├── .env.example                 # Sample environment variable definitions
├── requirements.txt             # Python dependencies
├── run.sh                       # Shell script to run the assistant
├── compile_prompt.py            # Script to compile the final prompt using context and personality data
├── personality_helper.py        # Helper script for managing personality profiles
└── setup.py                     # Package setup script
```

### Running Tests & Debugging

- **Testing:**  
  You can run individual plugins or add your own unit tests to verify new features.
- **Debugging:**  
  Insert breakpoints or use Python’s built-in `pdb` module within any script as needed.

---

## Contributing

Contributions are welcome! To contribute:

1. Fork the repository.
2. Create a new feature branch.
3. Commit your changes with clear messages.
4. Push your branch and open a pull request.

Please follow existing coding standards and add tests where applicable.

---

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more details.

---

## Acknowledgements

- Thanks to the maintainers and contributors of all third-party libraries used in this project.
- Special thanks to the developers behind the APIs (OpenWeatherMap, iCloud, ProtonMail, Strava, etc.) whose services make this assistant possible.
