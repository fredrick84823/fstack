---
description: Split an audio file into 10-minute segments and move to Downloads
---

Split the audio file specified by the user into 10-minute (600 second) segments using ffmpeg, then move all the output files to ~/Downloads.

Steps:
1. Ask the user for the input audio file path
2. Extract the base filename (without extension) to use for output naming
3. Use ffmpeg with the segment muxer to split the audio:
   - Input: user-provided file path
   - Format: segment
   - Segment time: 600 seconds (10 minutes)
   - Codec: copy (no re-encoding)
   - Output pattern: {basename}_output_%03d.{extension}
4. Move all generated segment files to ~/Downloads/

Example command structure:
```
ffmpeg -i "input_path" -f segment -segment_time 600 -c copy "output_path/basename_output_%03d.ext"
mv output_path/basename_output_*.ext ~/Downloads/
```
