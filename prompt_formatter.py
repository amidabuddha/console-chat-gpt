import sys


def replace_special_characters(filename):
    # Read the contents of the file and replace special characters
    with open(filename, 'r') as file:
        content = file.read().replace('\n', '\\n').replace('\"', '\\\"')

    # Create a new file with the modified content
    new_filename = f"{filename.split('.')[0]}_modified.txt"
    with open(new_filename, 'w') as file:
        file.write(content)

    print(f"Success! Modified content saved in {new_filename}")


# Get the filename as an argument
if len(sys.argv) < 2:
    print("Please provide the filename as an argument.")
else:
    filename = sys.argv[1]

# Call the function
replace_special_characters(filename)