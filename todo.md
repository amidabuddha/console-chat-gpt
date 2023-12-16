### Logical changes:

- [ ] Disallow SIGINT during session (just reload line to flush the STDIN)
- [ ] Disallow EOT (ctrl + D) cause why would you allow it :)

### Features

- [ ] Allow adding new models via interactive menu with `/models` endpoint
- [ ] Finish the settings menu
- [ ] Calculate used tokens and price
- [ ] Allow the user to control colors

### Optimization and clean up

- [ ] Check for trash code and unused vars/functions
- [ ] More detailed exceptions
- [ ] Disallow the user to send completion > max token

### To verify

- [x] When roles are 0 if all works
- [x] When models are 0 if all works

### Chores

- [x] Fix Readme.md

### Bugs

- [ ] STTY `-icrnl` breaking all STDIN
  ```python
  import subprocess

          def check_and_update_stty_settings():
              try:
                  # Capture the current stty settings
                  result = subprocess.run(['stty', '-a'], capture_output=True, text=True, check=True)
                  current_settings = result.stdout
        
                  # Check if -icrnl flag is set
                  if '-icrnl' in current_settings:
                      print("Warning: -icrnl flag is set. Attempting to change terminal settings...")
                      subprocess.run(['stty', 'icrnl'], check=True)
                      print("Terminal settings adjusted: -icrnl removed.")
                  else:
                      print("Terminal settings are already correct. No change needed.")
        
              except subprocess.CalledProcessError as e:
                  print(f"Failed to check or change terminal settings: {e}")
        
          # Call this function at the start of your script
          check_and_update_stty_settings()
      > Breaks the "ENTER" button (^M)

## Done

- [x] Handle SIGINT during "User:" phase properly
- [x] Save chat on exit
    - [x] Prompt
    - [x] Functionality
        - [x] Basic
        - [x] Clean up
- [x] Allow file upload
- [x] Allow multiline input
- [x] Add option to disable emojis
- [x] Clean up the config.toml
- [x] Docstring everything