#!/bin/sh
# Run an analysis tool from the spb-ci-tools image on the current directory.
exec docker run --rm -v "$PWD":"$PWD" -w "$PWD" spb-ci-tools "$@"