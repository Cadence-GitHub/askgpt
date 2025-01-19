#!/bin/python3

# For bash history to work correctly, you need to add this to your .bashrc:
# export PROMPT_COMMAND='history -a'   
# This will append the history to the history file every time a command is executed.

# You need to create your own AWS Bedrock credentials. If you want support for other APIs, let me know and I can add them.

### Installation:
# pip install boto3
# pip install humanize
# Copy this file to your OS in the /usr/local/bin/askgpt file and set correct permissions: chmod a+x /usr/local/bin/askgpt

### Usage:
# You can run the command askgpt in your terminal and it will ask you for your query and then it will give you the command to execute.
# You can also specify your query in the command line:
# askgpt "find all text files modified in the last 24 hours"    

# You can pipe data to the command:
# ps axuw|grep init | askgpt 
# or
# ps axuw|grep init | askgpt "explain what do the numbers mean in the output"


import boto3
import json
import sys
import re
import os
import subprocess
from datetime import datetime, timedelta
import humanize


# Create a session with your credentials
session = boto3.Session(
    aws_access_key_id='change_me',
    aws_secret_access_key='change_me',
    region_name='us-west-2'  # or 'us-west-2' depending on your region
)

# Create a Bedrock client
bedrock = session.client('bedrock-runtime')

def load_previous_interactions():
    try:
        history_file = os.path.expanduser('~/.askgpt_history')
        if os.path.exists(history_file):
            with open(history_file, 'r') as f:
                all_interactions = json.load(f)
                eighteen_hours_ago = datetime.now() - timedelta(hours=18)
                recent_interactions = []
                total_length = 0
                
                # Process interactions from newest to oldest
                for interaction in reversed(all_interactions):
                    if datetime.fromisoformat(interaction['timestamp']) > eighteen_hours_ago:
                        # Safely handle None values
                        query_len = len(interaction.get('query', '')) if interaction.get('query') is not None else 0
                        command_len = len(interaction.get('command', '')) if interaction.get('command') is not None else 0
                        explanation_len = len(interaction.get('explanation', '')) if interaction.get('explanation') is not None else 0
                        interaction_length = query_len + command_len + explanation_len
                        
                        if total_length + interaction_length > 5000:
                            break
                            
                        recent_interactions.insert(0, interaction)
                        total_length += interaction_length
                
                return recent_interactions
        return []
    except Exception as e:
        print(f"Warning: Could not load previous interactions: {e}")
        return []

def save_interactions(interactions):
    try:
        history_file = os.path.expanduser('~/.askgpt_history')
        with open(history_file, 'w') as f:
            json.dump(interactions, f, indent=2)
    except Exception as e:
        print(f"Warning: Could not save interactions: {e}")


def extract_answer(text, tag):
    pattern = f'<{tag}>(.*?)</{tag}>'
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    else:
        return None  # Return None instead of an error message
    


system_prompt = """You are a Linux command line expert. Your role is to generate shell commands based on natural language queries.

# Rules:
1. Respond ONLY with the exact command(s) to execute within the <command></command> tags - no explanations or additional text
2. For complex operations, you may use multiple lines with pipes (|) or semicolons (;)
3. Always use proper shell syntax and escaping
4. If multiple solutions exist, provide only the most efficient one
5. Do not include markdown formatting or code blocks in your response
6. When shell-specific features are available, prefer those over generic solutions
7.1 Always check the user's environment context provided in the <environment></environment> tags before suggesting commands:
   - Verify if the user has necessary permissions (root/sudo) for privileged commands
   - Consider the current working directory and available files
   - Use shell-specific features based on the user's shell
   - Consider recent command history to avoid redundant operations
   - Adapt commands based on the OS version and distribution
7.2 Use this information to provide commands that are:
   - Compatible with the user's environment
   - Respectful of user permissions
   - Contextually aware of the current directory
   - Efficient based on the available files and recent operations

# Output format:
1. Your response MUST contain these XML tags:
   <thinking>Step by step analysis of the problem and solution</thinking>
   <explanation>Clear explanation of what the command does and why you chose it</explanation>
   <command>The actual command(s) to execute</command>
2. Tag requirements:
   - <thinking>: Include your step-by-step reasoning (not shown to user)
   - <explanation>: Must be clear, concise, and explain any potential risks
   - <command>: Must contain ONLY the command(s) to execute, with no additional text

# Example:
Query: "find all text files modified in the last 24 hours"

Response: <thinking>
1. User needs to find text files
2. Check if they have sudo rights
3. Consider current directory context
4. Choose appropriate find command
</thinking>
<explanation>
This command searches for .txt files modified in the last 24 hours in your home directory.
It's safe to run and won't require elevated permissions.
</explanation>
<command>
find ~ -type f -name "*.txt" -mtime -1
</command>


# Before answering:
1. Think it through step-by-step within <thinking></thinking> tags
2. Provide a clear explanation of what the command does within <explanation></explanation> tags
3. Provide your final command within <command></command> tags
4. Keep in mind that the user will only see the text you output in the <command></command> tags and in the <explanation></explanation> tags. The user will not see anything else.

If uncertain, indicate you don't know rather than fabricate information.
"""


if len(sys.argv) < 2:
    print("Enter your query (press Ctrl+D when finished):")
    try:
        # Collect all input lines until EOF (Ctrl+D)
        query_lines = []
        while True:
            try:
                line = input()
                query_lines.append(line)
            except EOFError:
                break
        query = '\n'.join(query_lines)
        if not query.strip():
            print("No query provided. Exiting.")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\nInput cancelled. Exiting.")
        sys.exit(1)
else:
    # Check if there's data on stdin
    if not sys.stdin.isatty():
        stdin_data = sys.stdin.read().strip()
        query = f"{' '.join(sys.argv[1:])} \n\nInput: {stdin_data}"
    else:
        query = ' '.join(sys.argv[1:])

if len(query) > 1000:
    print("Error: Query is too long. Please limit your query to 1000 characters.")
    sys.exit(1)

print("\nProcessing your query...")

try:
    # Check if user has root privileges
    is_root = os.geteuid() == 0
    
    # Check if user has sudo rights
    has_sudo = False
    try:
        # Check sudo rights using -l flag to list privileges
        result = subprocess.run(['sudo', '-l'], 
                              capture_output=True, 
                              text=True, 
                              timeout=1)  # Add timeout to prevent hanging
        # User has some sudo privileges if command succeeds
        has_sudo = result.returncode == 0
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        # Command failed or timed out - user likely doesn't have sudo rights
        has_sudo = False
    except FileNotFoundError:
        # sudo is not installed
        has_sudo = False
    except Exception:
        # Catch any other unexpected errors
        has_sudo = False

    # Get Linux version information
    linux_version = None
    try:
        with open('/etc/os-release', 'r') as f:
            os_info = dict(line.strip().split('=', 1) for line in f if '=' in line)
            linux_version = os_info.get('PRETTY_NAME', '').strip('"')
    except:
        # Fallback method if /etc/os-release is not available
        try:
            linux_version = subprocess.check_output(['uname', '-r'], universal_newlines=True).strip()
            linux_version = f"Kernel version: {linux_version}"
        except:
            linux_version = None

    # Get shell history
    history = []
    try:
        # Check if PROMPT_COMMAND includes history -a
        prompt_command = os.getenv('PROMPT_COMMAND', '')
        history_synced = 'history -a' in prompt_command

        if not history_synced:
            history = []  # Skip history if not properly configured
        else:
            history_path = os.path.expanduser("~/.bash_history")
                
            # Check if the file exists
            if not os.path.isfile(history_path):
                print(f"Error: History file '{history_path}' does not exist.")
                history = []
            else:
                with open(history_path, 'r', encoding='utf-8', errors='ignore') as file:
                    # Filter out timestamp lines (starting with #) and empty lines
                    lines = [line.strip() for line in file.readlines() 
                            if line.strip() and not line.strip().startswith('#')]
                    
                    # Get last 10 entries
                    history = lines[-10:]
    except Exception as e:
        print(f"Debug - Exception: {str(e)}")
        history = [f'Unable to read history: {str(e)}']

    # Get current directory and files with details
    cwd = os.getcwd()
    try:
        # Get file details for all files in directory
        file_details = []
        for filename in os.listdir('.'):
            try:
                stat = os.stat(filename)
                file_details.append({
                    'name': filename,
                    'mtime': stat.st_mtime,
                    'perms': oct(stat.st_mode)[-3:],  # Unix style permissions
                    'size': stat.st_size,
                    'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M')
                })
            except Exception:
                continue
        
        # Sort by modification time (newest first) and take top 10
        file_details.sort(key=lambda x: x['mtime'], reverse=True)
        files_formatted = []
        for f in file_details[:10]:
            files_formatted.append(
                f"  {f['name']} ({f['perms']}, {f['modified']}, {humanize.naturalsize(f['size'])})"
            )
        
        if len(file_details) > 10:
            files_formatted.append('  ...')
            
        files_formatted = '\n'.join(files_formatted)
    except Exception as e:
        files_formatted = f'none (error: {str(e)})'

    # Create environment context
    os_info = f"OS: {linux_version}\n" if linux_version else ""
    environment_context = f"""Shell: {os.path.basename(os.getenv('SHELL', ''))}
{os_info}Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'User: ' + os.getenv('USER', os.getenv('USERNAME', '')) if os.getenv('USER') or os.getenv('USERNAME') else ''}
Root privileges: {'yes' if is_root else 'no'}
Sudo rights: {'yes' if has_sudo else 'no'}
{'Home: ' + os.path.expanduser('~') if os.path.expanduser('~') else ''}
Current directory: {cwd}"""
    environment_context += f"\nFiles in the current directory (10 most recent) [name (permissions, last modified, size)]:\n{files_formatted}"
    if history:
        environment_context += "\nLast 10 commands executed by the user:\n" + "\n".join(f"  {cmd}" for cmd in history)

    # Modify the system prompt to include environment context
    full_system_prompt = f"""{system_prompt}

Current Environment:
<environment>
{environment_context}
</environment>"""

    # Initialize conversation_history before the if statement
    previous_queries_and_answers = load_previous_interactions()
    conversation_history = []
    if previous_queries_and_answers:
        for interaction in previous_queries_and_answers:
            conversation_history.append({
                "role": "user",
                "content": interaction['query']
            })
            conversation_history.append({
                "role": "assistant",
                "content": f"<command>{interaction['command']}</command>\n<explanation>{interaction['explanation']}</explanation>"
            })
    
    def append_to_log(content):
        log_file = os.path.expanduser('~/.askgpt_log')
        with open(log_file, 'a') as f:
            f.write(f"\n{datetime.now().isoformat()}\n")
            f.write(content)
            f.write("\n" + "=" * 80 + "\n")

    append_to_log(f"User Query:\n{query}")
    append_to_log(f"System Prompt:\n{full_system_prompt}")
    
    response = bedrock.invoke_model(
        modelId='anthropic.claude-3-5-sonnet-20241022-v2:0',
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "temperature": 0,
            "max_tokens": 1024,
            "system": full_system_prompt,
            "messages": conversation_history + [
                {
                    "role": "user", 
                    "content": f"Query: {query}"
                }
            ]
        })
    )

    # Parse and print the response
    response_body = json.loads(response['body'].read())
    # Log the raw response instead of printing
    append_to_log(f"Raw Response:\n{response_body['content'][0]['text']}")

    command = extract_answer(response_body['content'][0]['text'], 'command')
    thinking = extract_answer(response_body['content'][0]['text'], 'thinking')
    explanation = extract_answer(response_body['content'][0]['text'], 'explanation')
    print('\n' + '=' * 80)
    print('EXPLANATION:')
    print('-' * 80)
    print(explanation)
    
    # Print answer with distinct separator
    print('\n' + '=' * 80)
    print('COMMAND:')
    print('-' * 80)
    print(command)
    print('=' * 80 + '\n')

    # Log the full response body at the end
    append_to_log(f"Full Response:\n{json.dumps(response_body, indent=2)}")

    current_interaction = {
        'query': query,
        'command': command,
        'explanation': explanation,
        'timestamp': datetime.now().isoformat()
    }
    
    # Update the previous interactions list
    previous_queries_and_answers.append(current_interaction)
    if len(previous_queries_and_answers) > 5:
        previous_queries_and_answers.pop(0)
    
    # Save the updated interactions
    save_interactions(previous_queries_and_answers)


    # Print full response after a few line breaks
    # print("\n\nFull Response:")
    # print(json.dumps(response_body, indent=2))

except Exception as e:
    print(f"Error: {e}")

