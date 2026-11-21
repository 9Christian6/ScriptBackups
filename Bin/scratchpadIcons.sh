#!/bin/bash
scratch=$(i3-msg -t get_tree | jq -r '.nodes[].nodes[].nodes[] | select(.name=="__i3_scratch") | .floating_nodes[].nodes[].window_properties.class' | sort -u | paste -sd,)
scratchString=""
IFS=',' read -ra apps <<< "$scratch"
for app in "${apps[@]}"; do
  value=$(grep "$app" "$CONFIG/workstyle/config.toml" | awk '{gsub(/"/, ""); print $3}' | sed 's/ //g')
  if [ -n "$value" ]; then
    if [ -n "$scratchString" ]; then
      scratchString="${scratchString} , ${value}"
    else
      scratchString="${value}"
    fi
  fi
done
echo $scratchString
