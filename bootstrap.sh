#!/bin/bash

# Create symlink for .bash_profile
ln -s /workspaces/.codespaces/.persistedshare/dotfiles/.bash_profile /home/vscode/.bash_profile

echo "source /home/vscode/.bash_profile" >> /home/vscode/.bashrc
