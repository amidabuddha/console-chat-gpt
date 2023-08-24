from console_mods.console_gpt import ConsoleGPT

if __name__ == "__main__":
    try:
        ConsoleGPT().main()
    except (KeyboardInterrupt, EOFError) as e:
        ConsoleGPT.custom_print("error", f"Caught interrupt!", 130)
