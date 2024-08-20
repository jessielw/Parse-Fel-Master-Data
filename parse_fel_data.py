import argparse
import re
import subprocess
import sys
from pathlib import Path
from pymediainfo import MediaInfo
from typing import Tuple, Optional, NewType


FormatStr = NewType("FormatStr", str)


class ParseFelDataError(Exception):
    """Class to catch expected errors from"""


def cli() -> Tuple[Path, Path, Path, bool]:
    parser = argparse.ArgumentParser()
    parser.add_argument("-r", "--rpu-input", type=str, help="Input file (RPU.bin)")
    parser.add_argument("-i", "--input", type=str, help="Input file (video.ext)")
    parser.add_argument(
        "-d", "--dovi-tool", type=str, help="Path to dovi_tool executable"
    )
    parser.add_argument(
        "-s",
        "--save",
        action="store_true",
        help="If passed will save the results to a text file beside the 'input'",
    )

    args = parser.parse_args()

    if not args.rpu_input or not Path(args.rpu_input).exists():
        print("'-r/--rpu-input' is required (RPU.bin)")
        sys.exit(1)

    if not args.input or not Path(args.input).exists():
        print("'-i/--input' is required (video.ext)")
        sys.exit(1)

    if not args.dovi_tool or not Path(args.dovi_tool).exists():
        print("'-d/--dovi-tool' is required")
        sys.exit(1)

    return Path(args.rpu_input), Path(args.input), Path(args.dovi_tool), args.save


def detect_master_display(file_input: Path) -> FormatStr:
    """
    Utilizes MediaInfo to detect the type of master-display string
    that's needed to be utilized with x265.

    Note: We are rounding down 'maximum_cll' and 'maximum_fall' values.

    Args:
        file_input (Path): File input (mkv/mp4/etc)

    Returns:
        str: Returns a string that is ready to be formatted with values.

    Example Usage:
    >>> master = detect_master_display(fp)
    >>> master = master.format(luminance_max=luminance_max, luminance_min=luminance_min)
    """
    try:
        media_info = MediaInfo.parse(file_input).video_tracks[0]
        mastering_display_color_primaries = media_info.mastering_display_color_primaries
        if not mastering_display_color_primaries:
            raise ParseFelDataError(
                "Input file doesn't contain any mastering display color primary data"
            )

        mastering_display_color_primaries = str(
            mastering_display_color_primaries
        ).lower()
        if "display p3" in mastering_display_color_primaries:
            return "G(13250,34500)B(7500,3000)R(34000,16000)WP(15635,16450)L({maximum_luma},{minimum_luma})"
        elif "dci p3" in mastering_display_color_primaries:
            return "G(13250,34500)B(7500,3000)R(34000,16000)WP(15700,17550)L({maximum_luma},{minimum_luma})"
        elif "bt.2020" in mastering_display_color_primaries:
            return "G(8500,39850)B(6550,2300)R(35400,14600)WP(15635,16450)L({maximum_luma},{minimum_luma})"
        else:
            raise ParseFelDataError(
                "Video doesn't appear to need a master-display string..."
            )

    except IndexError:
        raise ParseFelDataError("Input file is lacking a 'video track'")


def parse_dovi_tool_output(
    file_input: Path, dovi_tool_path: Path
) -> Tuple[float, float, float, float, str]:
    """Utilizes dovi_tool to output a summary and parse key data needed from the RPU for FEL."""
    command = (str(dovi_tool_path), "info", "-i", str(file_input), "-s")

    get_output = subprocess.run(
        command, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True
    )
    if get_output.returncode != 0:
        raise ParseFelDataError(
            f"Failed to execute command with dovi_tool (error code: {get_output.returncode})"
        )

    full_summary = ""
    summary = get_output.stdout.split("Summary:\n")[1].strip().splitlines()
    rpu_mastering_display = ""
    rpu_content_light_level = ""

    for item in summary:
        item = item.strip()
        full_summary = full_summary + item + "\n"
        if "RPU mastering display" in item:
            rpu_mastering_display = item
        elif "RPU content light level" in item:
            rpu_content_light_level = item

    if not rpu_mastering_display or not rpu_content_light_level:
        raise ParseFelDataError(
            f"Failed to detect 'RPU mastering display' or 'RPU content light level'"
        )

    minimum_luma = None
    maximum_luma = None
    maximum_cll = None
    maximum_fall = None

    split_luma = re.search(r"display:\s(.+?)/(.+?)\snits", rpu_mastering_display)
    if split_luma:
        minimum_luma = float(split_luma.group(1))
        maximum_luma = float(split_luma.group(2))

    split_light_level = re.search(
        r"MaxCLL:\s(.+?)\snits,\sMaxFALL:\s(.+?)\snits", rpu_content_light_level
    )
    if split_light_level:
        maximum_cll = float(split_light_level.group(1))
        maximum_fall = float(split_light_level.group(2))

    # check to ensure we've detected ALL needed values
    if any(
        not item for item in (minimum_luma, maximum_luma, maximum_cll, maximum_fall)
    ):
        raise ParseFelDataError(
            "One or more of the values could not be detected from the input file "
            f"(min-luma: {minimum_luma if minimum_luma else 'Not Found'}, "
            f"max-luma: {maximum_luma if maximum_luma else 'Not Found'}, "
            f"max-cll: {maximum_cll if maximum_cll else 'Not Found'}, "
            f"max-fall: {maximum_fall if maximum_fall else 'Not Found'})"
        )

    return (
        round(minimum_luma * 10000),
        round(maximum_luma * 10000),
        round(maximum_cll),
        round(maximum_fall),
        full_summary.strip(),
    )


final_str = """\
Dovi_tool Summary:
{summary}

Maximum CLL: {maximum_cll}

Maximum FALL: {maximum_fall}

Master Display: {master_display}"""


def generate_info(
    rpu_input: Path,
    file_input: Path,
    dovi_tool_path: Path,
    save: bool,
    final_str: FormatStr,
) -> None:
    try:
        minimum_luma, maximum_luma, maximum_cll, maximum_fall, summary = (
            parse_dovi_tool_output(rpu_input, dovi_tool_path)
        )
        master_display = detect_master_display(file_input)
        master_display = master_display.format(
            maximum_luma=maximum_luma, minimum_luma=minimum_luma
        )

        final_str = final_str.format(
            summary=summary,
            maximum_cll=maximum_cll,
            maximum_fall=maximum_fall,
            master_display=master_display,
        )
        if save:
            with open(
                file_input.with_name(f"{file_input.stem}_fel_data.txt"), "w", encoding="utf-8"
            ) as save_out:
                save_out.write(final_str)
        print(final_str)

        sys.exit(0)
    except ParseFelDataError as error:
        print(error)
    except Exception as unhandled_error:
        print(f"There was an unexpected error: {unhandled_error}")
    sys.exit(1)


if __name__ == "__main__":
    generate_info(*cli(), final_str)
