# encoder-dotnet
Plug-in dotnet settings encoder for servo

# Usage
_Dev Notes: running pytest will generate files with example output_

When you will be packaging an adjust driver with IIS 8 settings driver, please copy `encoders/dotnet.py` to your final package's `encoders/` folder. 
Follow further packaging steps you can find in the repo `opsani/servo`.

# Available settings and their defaults

TODO

## Important notes on configuring settings

TODO

# How to run tests
Prerequisites:
* Python 3.5 or higher
* PyTest 4.3.0 or higher

Follow these steps: (NOTE: small tweaks have been made to the base.py herein that should be backwards compatible)
1. Pull the repository
2. Copy `base.py` from `https://github.com/opsani/servo/tree/master/encoders` to folder `encoders/`
3. Run `pytest` from the root folder
