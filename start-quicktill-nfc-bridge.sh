#!/bin/bash

set -e

if [ "${ACTION}" = "add" ]; then
  /lib/quicktill-nfc-bridge/quicktill-nfc-bridge &
fi
