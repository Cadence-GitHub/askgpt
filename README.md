# AskGPT CLI

A powerful command-line interface that leverages Claude 3.5 Sonnet to generate and explain Linux shell commands from natural language queries. Simply describe what you want to do, and AskGPT will provide the exact command along with a clear explanation.

## Key Features
- Natural language to shell command translation
- Context-aware command generation based on your current environment
- Command history integration for smarter suggestions
- Support for piped input data
- Maintains conversation history for more relevant responses
- Detailed explanations for every suggested command

## Prerequisites

- Python 3.7 or higher
- AWS credentials
- Bash shell environment

## Installation

1. Install required Python packages:
```bash
pip install boto3 humanize
```

2. Copy the script to your system:
```bash
sudo cp askgpt.py /usr/local/bin/askgpt
sudo chmod a+x /usr/local/bin/askgpt
```

3. Configure bash history integration by adding this line to your `~/.bashrc`:
```bash
export PROMPT_COMMAND='history -a'
```

4. Reload your bash configuration:
```bash
source ~/.bashrc
```

## Usage

### Basic Query
Simply run the command without arguments to enter interactive mode:
```bash
askgpt
```

### Direct Query
Provide your query directly as an argument:
```bash
askgpt "find all text files modified in the last 24 hours"
```

### Piped Input
You can pipe command output to AskGPT for explanation or further processing:
```bash
ps axuw | grep init | askgpt
```

Or add a specific query for the piped data:
```bash
ps axuw | grep init | askgpt "explain what these numbers mean"
```

## Examples

1. Finding files:
```bash
askgpt "find all PNG files larger than 1MB"
```

2. System monitoring:
```bash
askgpt "show me CPU usage for all processes sorted by usage"
```

3. Text processing:
```bash
cat log.txt | askgpt "extract all IP addresses"
```

## Configuration

The tool uses your AWS credentials for API access. If you want support for more APIs, let me know (or propose a pull request).



## Contributing

Feel free to submit issues and pull requests to improve AskGPT CLI.


