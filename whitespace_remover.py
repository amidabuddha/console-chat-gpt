def replace_special_characters(filename):
    # Read the contents of the file
    with open(filename, 'r') as file:
        content = file.read()

    # Replace newline characters with \n and " with \"
    content = content.replace('\n', '\\n').replace('"', '\\"')

    # Create a new file with the modified content
    new_filename = filename.split('.')[0] + '_modified.txt'
    with open(new_filename, 'w') as file:
        file.write(content)

    print(f'Success! Modified content saved in {new_filename}')

# Prompt the user for the filename
filename = input("Enter the filename: ")

# Call the function
replace_special_characters(filename)