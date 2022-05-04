#!/bin/bash

# Create symlink for .bash_profile
rm /home/vscode/.bashrc
ln -s /workspaces/.codespaces/.persistedshare/dotfiles/.bash_profile /home/vscode/.bashrc
