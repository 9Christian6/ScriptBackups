#!/bin/bash

if [ -z "$1" ]; then
    echo "Usage: $0 <document name>"
    exit 1
fi

FILENAME="${pwd}$1.tex"
cp $HOME/Documents/Uni/LaTeXTemplate.tex $FILENAME
nvim $FILENAME
