- [ ] Optimization and Clean up
- [x] Handle SIGINT during "User:" phase properly
- [x] Save chat on exit 
  - [x] Prompt
  - [x] Functionality
    - [x] Basic
    - [x] Clean up
- [x] Allow file upload
- [x] Allow multiline input
- [ ] Single file for handling exit/info messages
- [ ] More detailed exceptions
- [ ] Handle:
    - [ ] When roles are 0
    - [ ] When models are 0
        - [ ] STTY `-icrnl`
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

- [ ] Calculate used tokens and price
- [ ] Add option to disable emojis
- [ ] Clean up the config.toml
- [ ] Allow the user to control colors
- [ ] Docstring everything
- [ ] Check for trash code and unused vars/functions
- [ ] Disallow the user to send completion > max token
- [ ] Fix Readme.md 
