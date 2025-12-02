## A package for defining common cross project utilities
### What does it include
- MQTT utils
- Metrics utils
- Schemas
- Network utils
### How to use and install the package
Within the root of. project that requires the package run poetry add ../common
If you make changes to the common package and want these to be reflected you'll need to cd into the outer common folder, e.g from a project cd ../common
Once in the folder run `poetry install`
Then cd back into the project you want to use common in and run `poetry remove common` followed by `poetry add ../common`