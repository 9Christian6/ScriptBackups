#!/bin/bash
killall workstyle&
wait
exec $HOME/.cargo/bin/workstyle&
