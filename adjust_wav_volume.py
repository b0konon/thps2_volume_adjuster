# adjust_wav_volume.py
#!/usr/bin/env python3

import wave
import numpy as np
import sys
import os
import argparse

def adjust_volume(input_wav_path, output_wav_path, factor):
    """
    Reads a WAV file, adjusts its volume by a factor, and saves it to a new file.

    Args:
        input_wav_path (str): Path to the input WAV file.
        output_wav_path (str): Path to save the modified WAV file.
        factor (float): Volume adjustment factor (e.g., 0.5 for 50% volume,
                        1.0 for no change, 2.0 for double volume - risks clipping).
    """
    try:
        with wave.open(input_wav_path, 'rb') as wf:
            params = wf.getparams()
            n_channels, sampwidth, framerate, n_frames, comptype, compname = params

            if comptype != 'NONE':
                print(f"Error: Unsupported compression type '{comptype}' in {input_wav_path}. Only PCM supported.", file=sys.stderr)
                return False

            frames = wf.readframes(n_frames)

            dtype = np.int16

            audio_data = np.frombuffer(frames, dtype=dtype)

            adjusted_data = audio_data.astype(np.float64) * factor

            min_val = np.iinfo(dtype).min
            max_val = np.iinfo(dtype).max
            adjusted_data = np.clip(adjusted_data, min_val, max_val)

            adjusted_data = adjusted_data.astype(dtype)

            adjusted_frames = adjusted_data.tobytes()

        with wave.open(output_wav_path, 'wb') as wf_out:
            wf_out.setparams(params)
            wf_out.writeframes(adjusted_frames)

        print(f"Successfully adjusted volume for '{input_wav_path}' and saved to '{output_wav_path}' (Factor: {factor})")
        return True

    except wave.Error as e:
        print(f"Error processing WAV file {input_wav_path}: {e}", file=sys.stderr)
        return False
    except FileNotFoundError:
        print(f"Error: Input file not found: {input_wav_path}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Adjust the volume of a WAV file.")
    parser.add_argument("input_wav", help="Path to the input WAV file.")
    parser.add_argument("factor", type=float, help="Volume adjustment factor (e.g., 0.5 for 50% volume).")
    parser.add_argument("-o", "--output", help="Path for the output WAV file (default: adds '_adj' suffix).")

    args = parser.parse_args()

    if args.output:
        output_wav = args.output
    else:
        base, ext = os.path.splitext(args.input_wav)
        output_wav = f"{base}_adj{ext}"

    if not adjust_volume(args.input_wav, output_wav, args.factor):
        sys.exit(1) 