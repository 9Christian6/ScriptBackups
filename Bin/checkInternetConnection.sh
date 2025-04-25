#!/bin/bash
lookupResult=$(exec nslookup google.com|grep Name|head -n 1)
if [ -n "$lookupResult" ]; then
  echo "0"
else
  echo "1"
fi
