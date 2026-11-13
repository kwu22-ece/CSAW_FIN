"""Reference-command contract fixture ONLY: identity, not a recovered FIR model."""
import pathlib
import shutil
import sys

source, destination = map(pathlib.Path, sys.argv[1:])
shutil.copyfile(source, destination)
