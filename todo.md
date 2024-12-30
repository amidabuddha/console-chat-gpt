### Optimization and clean up

- [ ] Check for trash code and unused vars/functions
- [ ] More detailed exceptions
- [ ] Disallow the user to send completion > max token

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
- [x] ~~Disallow SIGINT during session (just reload line to flush the STDIN)~~ Handle SIGINT globally
- [x] Disallow EOT (ctrl + D) cause why would you allow it :)
- [x] When roles are 0 if all works
- [x] When models are 0 if all works
- [x] Fix Readme.md
- [x] ~~STTY `-icrnl` breaking all STDIN~~ Not reproducible
