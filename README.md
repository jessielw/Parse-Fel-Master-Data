# Parse-Fel-Master-Data

Simple CLI to parse Dolby Vision master data via the RPU/MediaInfo and output data needed for x265

## Usage

```
usage: ParseFelData [-h] [-v] [-r RPU_INPUT] [-i INPUT] [-d DOVI_TOOL] [-s]

options:
  -h, --help            show this help message and exit
  -v, --version         show program's version number and exit
  -r RPU_INPUT, --rpu-input RPU_INPUT
                        Input file (RPU.bin)
  -i INPUT, --input INPUT
                        Input file (video.ext)
  -d DOVI_TOOL, --dovi-tool DOVI_TOOL
                        Path to dovi_tool executable
  -s, --save            If passed will save the results to a text file beside the 'input'
```

## Requirements

You will need to have [dovi_tool](https://github.com/quietvoid/dovi_tool) to utilize this utility. At the moment
this expects you already have the RPU extracted via dovi_tool as an input here.
