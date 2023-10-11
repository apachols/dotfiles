#!/bin/bash

# Create symlink for .bash_profile
ln -s /workspaces/.codespaces/.persistedshare/dotfiles/.bash_profile /home/$USER/.bash_profile

echo "source /home/$USER/.bash_profile" >> /home/$USER/.bashrc

cat /workspaces/.codespaces/.persistedshare/dotfiles/.gitconfig >> /home/$USER/.gitconfig