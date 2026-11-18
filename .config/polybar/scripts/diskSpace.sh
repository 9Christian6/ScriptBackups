#!/bin/bash
df -B1 / | awk 'NR==2 {printf "%.0f GB / %.0f GB\n", $3/1e9, $2/1e9}'
