#!/usr/bin/env bash
# Creates the SDD directory structure in the current project.
# Called by the dev-toolkit:sdd skill during the `add` phase.
set -e

mkdir -p .specs/tasks/draft
mkdir -p .specs/tasks/todo
mkdir -p .specs/tasks/in-progress
mkdir -p .specs/tasks/done
mkdir -p .specs/scratchpad

# Add scratchpad to .gitignore (temporary work files should not be committed)
if [ -f .gitignore ]; then
  if ! grep -q "\.specs/scratchpad" .gitignore; then
    echo ".specs/scratchpad/" >> .gitignore
    echo "Added .specs/scratchpad/ to .gitignore"
  fi
else
  echo ".specs/scratchpad/" > .gitignore
  echo "Created .gitignore with .specs/scratchpad/"
fi

echo "SDD directories created at .specs/"
