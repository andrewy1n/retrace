#!/usr/bin/env bash
# Stands in for the droid binary as the SDK's execPath. Runs droid inside the container named by RETRACE_CONTAINER, in RETRACE_WORKDIR (default /testbed).
exec docker exec -i -w "${RETRACE_WORKDIR:-/testbed}" -e FACTORY_API_KEY -e FACTORY_UPSTREAM_CLIENT_TYPE -e FACTORY_UPSTREAM_SDK \
  -e RETRACE_CAPTURE_DIR=/retrace/capture "${RETRACE_CONTAINER:?}" droid "$@"
