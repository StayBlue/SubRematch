from asyncio import subprocess
import srt, srt_tools.utils
import json
import subprocess
import sys
import os
import re

def prompt_choices(prompts: list, question: str) -> int:
    # Get all the indices of the prompts list
    for index in range(len(prompts)):
        prompt = prompts[index]

        # Print all the prompts
        if index == 0:
            print(f"[1] {prompt} (default)")

            continue

        print(f"[{index + 1}] {prompt}")

    # Question input
    choice = input(f"{question}: ").strip()

    # Check if the string is empty before conversion
    if choice != "":
        # Try-catch for conversion from string to integer (in case they input a string)
        try:
            choice = int(choice)
        except:
            print("Casting from a string to an integer failed.")

    if type(choice) == str or not prompts[choice - 1]:
        print("Invalid option selected, defaulting to default option...")

        choice = 1
    
    return choice

def remove_matches(matches: list, text: str) -> str:
    for match in matches:
        text = re.sub(match, "", text)

    return text

def remove_styling(subtitle_path: str) -> str:
    subtitle_file = open(subtitle_path, "r")

    file_content = subtitle_file.read()

    # Create a list of the subtitles
    subtitle_data = list(srt.parse(remove_matches(["<[^<]+?>", "{[^}]*}"], file_content)))

    # Normalize the subtitles
    subtitle_data = srt_tools.utils.compose_suggest_on_fail(subtitle_data, True)

    subtitle_file.close()

    subtitle_file = open(subtitle_path, "w")

    # Used the now normalized subtitles and remove all styling (<>) and curly brackets ({})
    subtitle_file.write(subtitle_data)

    subtitle_file.close()

def convert_to_srt(subtitle_path: str) -> str | None:
    if not subtitle_path.endswith(".srt"):
        # Replace the last four characters in the string (the file extension) with .srt
        subtitle_srt = subtitle_path.replace(subtitle_path[len(subtitle_path) - 4:], ".srt")

        # Use ffmpeg to convert the subtitle to a .srt
        subprocess.run(["ffmpeg", "-i", subtitle_path, subtitle_srt])

        return subtitle_srt

def extract_subs(video_path: str) -> str:
    # Get the track with the subtitles, and convert the output to a readable Json
    result = json.loads(subprocess.run(["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", "-select_streams", "s", video_path], check=True, capture_output=True).stdout.decode("utf_8"))

    index = None

    # Make a dictionary which can be indexed by the index of the individual streams
    streams = {stream["index"]: stream for stream in result["streams"]}

    if not result["streams"]:
        raise Exception(f"No subtitles found in any of the tracks! File path: {video_path}")
    elif len(result["streams"]) == 1:
        # If there is only one stream, we can easily get the index of the one stream
        index = result["streams"][0]["index"]
    else:
        # Allow the user to pick the correct stream if there are more than one streams
        print("Multiple streams detected! Requiring manual user input...")

        stream_prompts = []

        for stream in result["streams"]:
            stream_prompts.append("Index: {}\nCodec Name: {}\nTags: {}".format(stream["index"], stream["codec_name"], stream["tags"]))

        index = result["streams"][prompt_choices(stream_prompts, "Pick the correct stream") - 1]["index"]

    stream = streams[index]
    codec_name = stream["codec_name"]
    
    # Convert the codec name to the actual file extension (in case they aren't the same)
    if codec_name == "subrip":
        codec_name = "srt"

    if codec_name not in ("srt", "ass", "ssa", "idx"):
        print("The subtitle format provided in the video is not supported by Alass.")
        print(f"Please select a format other than {codec_name} next time...")
        print("Closing...")

        sys.exit(1)
    
    extracted_path = video_path.replace(".mkv", f".EXTRACTED.{codec_name}")

    subprocess.run(["mkvextract", "tracks", video_path, f"{index}:{extracted_path}"])

    return extracted_path

amount_choice = prompt_choices(["One File", "Multiple Files"], "Input how many files you are working with")

subtitle_paths = []

video_paths = []

if amount_choice == 1:
    subtitle_path = None

    while not subtitle_path:
        subtitle_input = input("Input the file path of the subtitle file: ").strip()

        # Check if they provided a valid file
        if not os.path.isfile(subtitle_input):
            print("Invalid file path provided, retrying...")

            continue

        # Check the extension and make sure it's a supported subtitle format
        if subtitle_input[len(subtitle_input - 3):] not in ("srt", "ass", "ssa", "idx"):
            print("Unsupported file format provided, retrying...")

            continue

        subtitle_path = subtitle_input

    video_path = None

    while not video_path:
        video_input = input("Input the video path of the video: ").strip()

        # Check if they provided a valid file
        if not os.path.isfile(video_input):
            print("Invalid file path provided, retrying...")
            
            continue 

        # Check if it is an mkv
        if not video_input.endswith(".mkv"):
            print("Only .mkv is supported, retrying...")

            continue
            
        video_path = video_input

    subtitle_paths.append(subtitle_path)

    video_paths.append(video_path)
elif amount_choice == 2:
    subtitle_prompts = [".srt", ".ass"]

    subtitle_choice = subtitle_prompts[prompt_choices(subtitle_prompts, "What is the file format of the Subtitle file you are attempting to embed?") - 1]

    # Gets all the files in the current working directory
    files = os.listdir()

    # We can guess the order of the subtitles and the video files based on the order in which they appear
    subtitle_paths = sorted([file for file in files if file.endswith(subtitle_choice)])

    video_paths = sorted([file for file in files if file.endswith(".mkv")])

    # Check if there is an equal amount of videos and subtitles
    length_subtitles = len(subtitle_paths)

    length_video = len(video_paths)

    if length_subtitles != length_video:
        print("Mismatched number of files found!")
        print(f"There are {length_subtitles} {subtitle_choice} files while there are {length_video} .mkv files.")
        print("Please make sure there are an equal amount of files for both subtitles and videos")
        input("Press any key to exit.")

        exit()

warning_choice = prompt_choices(["Yes", "No"], "WARNING: This program will remove any styling from provided subtitle files, and convert your existing subtitles to .srt files.\nDo you still wish to continue?")

embed_choice = prompt_choices(["ffmpeg, mkvtoolnix"], "Due to a strange issue with ffmpeg, you can have the option to use mkvmerge instead of ffmpeg if it somehow fails.\nWhich one would you like to use?")

if warning_choice == 1:
    print("Extracting subtitles from provided video(s)...")
    print("This may take a while.")

    extracted_paths = []

    for video_path in video_paths:
        extracted_paths.append(extract_subs(video_path))

    print("Extraction complete! Converting provided subtitles to .srt (if necessary)...")

    provided_converted_paths = []

    provided_converted_counter = 0

    for subtitle_path in subtitle_paths:
        provided_converted_path = convert_to_srt(subtitle_path)

        if provided_converted_path:
            provided_converted_paths.append(provided_converted_path)

            # Remove the non-converted file
            os.remove(subtitle_path)

            provided_converted_counter += 1
        else:
            provided_converted_paths.append(subtitle_path)

    print(f"Converted {provided_converted_counter} provided subtitle file(s) to .srt.")

    converted_paths = []

    converted_counter = 0

    print("Converting extracted subtitles to .srt (if necessary)...")

    for extracted_path in extracted_paths:
        converted_path = convert_to_srt(extracted_path)

        if converted_path:
            converted_paths.append(converted_path)

            # Remove the non-converted file
            os.remove(extracted_path)

            converted_counter += 1
        else:
            converted_paths.append(extracted_path)

    print(f"Converted {converted_counter} extracted subtitle file(s) to .srt.")

    print("Removing any styling from provided subtitles...")

    for provided_converted_path in provided_converted_paths:
        remove_styling(provided_converted_path)

    print("Removing any styling from extracted subtitles...")

    for converted_path in converted_paths:
        remove_styling(converted_path)

    print("Retiming...")

    retimed_paths = []

    # Use alass, the extracted subtitles, and the provided subtitles
    for index in range(len(video_paths)):
        retimed_path = provided_converted_paths[index].replace(subtitle_path[len(subtitle_path) - 4:], ".RETIMED.srt")

        subprocess.run(["alass-cli", converted_paths[index], provided_converted_paths[index], retimed_path])

        retimed_paths.append(retimed_path)

    print("Embedding subtitles...")

    # Embed the subtitles into the video using ffmpeg
    for index in range(len(video_paths)):
        if embed_choice == 1:
            subprocess.run(["ffmpeg", "-i", video_paths[index], "-i", retimed_paths[index], "-map", "0:0", "-map", "0:1", "-map", "1:0", "-c:v", "copy", "-c:a", "copy", "-c:s", "srt", video_paths[index].replace(".mkv", ".jp.mkv")])
        else:
            subprocess.run(["mkvmerge", "-o", video_paths[index].replace(".mkv", ".jp.mkv"), video_paths[index], retimed_paths[index]])

    clean_choice = prompt_choices(["Yes", "No"], "Done! Would you like to clean up?")

    if clean_choice == 1:
        # Cleanup
        print("Cleaning up...")

        for index in range(len(video_paths)):
            # Remove the old video
            os.remove(video_paths[index])
            # Removed the extracted, converted, reference subtitles
            os.remove(converted_paths[index])
            # Remove the converted provided subtitles
            os.remove(provided_converted_paths[index])

    print("Complete!")