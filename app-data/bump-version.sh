#!/bin/bash

# Function to extract and increment the version number
CONFIG_FILE="version.toml"
increment_version() {
    local version=$1
    local major=$(echo $version | cut -d. -f1)
    local minor=$(echo $version | cut -d. -f2)
    local patch=$(echo $version | cut -d. -f3)

    case $2 in
        "patch")
            let patch=patch+1
            ;;
        "minor")
            let minor=minor+1
            patch=0
            ;;
    esac

    echo "${major}.${minor}.${patch}"
}

# Get the last commit message
last_commit_message=$(git log -100 --pretty=%B)

current_version=$(awk '($1 == "version") {print $3}' $CONFIG_FILE | tr -d '"')
echo -e "Current version: $current_version"
# Magic regex
if grep -iqE "(\[improvement(s)?\]|\[bug(\s)?fix(es)?\])"<<<$last_commit_message; then
    new_version=$(increment_version $current_version "patch")
elif grep -iqE "\[feature(s)?\]"<<<$last_commit_message; then
    new_version=$(increment_version $current_version "minor")
else
    echo "Nothing to do. Version remains the same." && exit 0
fi
echo -e "New version: $new_version"
echo "version = \"$new_version\"" > $CONFIG_FILE
