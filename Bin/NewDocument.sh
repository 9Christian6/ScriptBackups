#!/bin/bash

if [ -z "$1" ]; then
    echo "Usage: $0 <document name>"
    exit 1
fi

sheetNumber="$2"

FILENAME="$(pwd)/$1.tex"
cp $HOME/Documents/Uni/LaTeXTemplate.tex $FILENAME
sed -i "s/SHEETNUMBER/${sheetNumber}/g" "$FILENAME"
nvim $FILENAME
