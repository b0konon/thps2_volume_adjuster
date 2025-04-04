import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
from tkinter import messagebox
import os
import sys
import threading
import queue
import shutil

try:
    script_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in locals() else '.'
    if script_dir not in sys.path:
        sys.path.append(script_dir)
    from extract_pkr import extract_pkr
    from adjust_wav_volume import adjust_volume
    from repack_pkr import repack_pkr
except ImportError as e:
    messagebox.showerror("Import Error", f"Failed to import necessary functions.\nEnsure 'extract_pkr.py', 'adjust_wav_volume.py', and 'repack_pkr.py' are in the same directory.\nError: {e}")
    sys.exit(1)
except FileNotFoundError as e:
     messagebox.showerror("Import Error", f"Failed to find necessary script files.\nEnsure 'extract_pkr.py', 'adjust_wav_volume.py', and 'repack_pkr.py' are in the same directory.\nError: {e}")
     sys.exit(1)

class PKRVolumeAdjusterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("THPS2 Volume Adjuster")
        self.root.geometry("550x350")

        self.pkr_file_path = tk.StringVar()
        self.volume_factor = tk.DoubleVar(value=0.5)
        self.status_text = tk.StringVar(value="Status: Idle")
        self.is_processing = False
        self.output_dir = "out"

        main_frame = ttk.Frame(root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        file_frame = ttk.LabelFrame(main_frame, text="Select ALL.PKR File", padding="10")
        file_frame.pack(fill=tk.X, pady=5)

        ttk.Entry(file_frame, textvariable=self.pkr_file_path, width=50, state="readonly").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Button(file_frame, text="Browse...", command=self.browse_pkr_file).pack(side=tk.LEFT)

        volume_frame = ttk.LabelFrame(main_frame, text="Volume Factor (Lower is Quieter)", padding="10")
        volume_frame.pack(fill=tk.X, pady=5)

        self.volume_slider = ttk.Scale(volume_frame, from_=0.0, to=1.0, orient=tk.HORIZONTAL, variable=self.volume_factor, command=self.update_slider_label)
        self.volume_slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.slider_label = ttk.Label(volume_frame, text=f"{self.volume_factor.get():.2f}", width=5)
        self.slider_label.pack(side=tk.LEFT)


        action_frame = ttk.Frame(main_frame, padding="5")
        action_frame.pack(fill=tk.X, pady=10)
        self.process_button = ttk.Button(action_frame, text="Create patched ALL.PKR", command=self.start_processing, state=tk.DISABLED)
        self.process_button.pack()

        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=(10, 0))
        ttk.Label(status_frame, textvariable=self.status_text).pack(side=tk.LEFT)
        self.progress_bar = ttk.Progressbar(status_frame, orient=tk.HORIZONTAL, mode='indeterminate')

    def browse_pkr_file(self):
        file_path = filedialog.askopenfilename(
            title="Select Input PKR File",
            filetypes=[("PKR Files", "*.pkr"), ("All Files", "*.*")]
        )
        if file_path:
            self.pkr_file_path.set(file_path)
            self.process_button.config(state=tk.NORMAL)

    def update_slider_label(self, value):
        self.slider_label.config(text=f"{float(value):.2f}")

    def start_processing(self):
        if not self.pkr_file_path.get():
            messagebox.showerror("Error", "Please select an input PKR file first.")
            return
        if self.is_processing:
            messagebox.showwarning("Busy", "Processing is already in progress.")
            return

        target_output_file = "ALL.PKR"
        if os.path.exists(target_output_file):
             if not messagebox.askyesno("Overwrite Confirmation",
                                     f"The file '{target_output_file}' already exists in this directory.\n"
                                     "Continuing will overwrite it after processing.\n\n"
                                     "Do you want to proceed?"):
                self.status_text.set("Status: Overwrite cancelled by user.")
                return

        self.is_processing = True
        self.process_button.config(state=tk.DISABLED)
        self.status_text.set("Status: Processing...")
        self.progress_bar.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(10, 0))
        self.progress_bar.start()
        self.result_queue = queue.Queue()
        self.processing_thread = threading.Thread(
            target=self.processing_worker,
            args=(self.pkr_file_path.get(), self.volume_factor.get(), self.result_queue),
            daemon=True
        )
        self.processing_thread.start()
        self.root.after(100, self.check_processing_queue)


    def check_processing_queue(self):
        try:
            message, is_complete, is_error = self.result_queue.get_nowait()
            self.status_text.set(f"Status: {message}")
            if is_complete:
                self.is_processing = False
                self.process_button.config(state=tk.NORMAL)
                self.progress_bar.stop()
                self.progress_bar.pack_forget()
                if is_error:
                     messagebox.showerror("Error", message)
                else:
                     messagebox.showinfo("Success", message)
            else:
                 self.root.after(100, self.check_processing_queue)
        except queue.Empty:
             if self.is_processing:
                self.root.after(100, self.check_processing_queue)


    def processing_worker(self, pkr_path, factor, result_queue):
        """Worker function to run in a separate thread."""
        repack_success = False
        repacked_file_path = "ALL.PKR"
        final_message = ""
        try:
            if os.path.exists(self.output_dir):
                 result_queue.put((f"Removing existing '{self.output_dir}' directory...", False, False))
                 print(f"DEBUG: Removing existing '{self.output_dir}' directory before extraction...")
                 try:
                     shutil.rmtree(self.output_dir)
                 except OSError as e:
                     print(f"Warning: Failed to remove existing '{self.output_dir}': {e}", file=sys.stderr)
                     result_queue.put((f"Warning: Failed to remove old '{self.output_dir}'", False, True))
            
            result_queue.put(("Extracting PKR...", False, False))
            if not extract_pkr(pkr_path, self.output_dir):
                raise RuntimeError(f"Extraction failed. Check console output for details.")
            
            audio_dir = os.path.join(self.output_dir, "audio")
            wav_files_found = False
            processed_count = 0
            error_count = 0
            total_files = 0
            volume_adj_summary = "No audio files processed."

            if os.path.isdir(audio_dir):
                result_queue.put(("Adjusting WAV volumes...", False, False))
                wav_files = [f for f in os.listdir(audio_dir) if f.lower().endswith(".wav")]
                if wav_files:
                    wav_files_found = True
                    total_files = len(wav_files)
                    for idx, wav_file in enumerate(wav_files):
                        input_wav = os.path.join(audio_dir, wav_file)
                        output_wav = input_wav # Overwrite
                        progress_msg = f"Processing WAV {idx+1}/{total_files}: {wav_file}"
                        result_queue.put((progress_msg, False, False))
                        if not adjust_volume(input_wav, output_wav, factor):
                            print(f"Error adjusting volume for {wav_file}. Skipping.", file=sys.stderr)
                            error_count += 1
                        else:
                            processed_count +=1
                    volume_adj_summary = f"{processed_count}/{total_files} WAV files adjusted."
                    if error_count > 0:
                        volume_adj_summary += f" ({error_count} errors)"
                else:
                     result_queue.put(("No .wav files found in audio directory. Skipping volume adjustment.", False, False))
                     volume_adj_summary = "No .wav files found in audio directory."
            else:
                result_queue.put(("No 'audio' directory found in extracted files. Skipping volume adjustment.", False, False))
                print(f"Debug: Contents of '{self.output_dir}' after extraction: {os.listdir(self.output_dir)}")
                volume_adj_summary = "No 'audio' directory found for adjustment."

            result_queue.put((f"Repacking files into {repacked_file_path}...", False, False))
            print(f"DEBUG: Calling repack_pkr(input_dir='{self.output_dir}', output_pkr_file='{repacked_file_path}')")

            if repack_pkr(self.output_dir, repacked_file_path):
                print("DEBUG: repack_pkr returned True")
                repack_success = True

                result_queue.put((f"Cleaning up temporary directory '{self.output_dir}'...", False, False))
                try:
                    shutil.rmtree(self.output_dir)
                    print(f"DEBUG: Successfully removed '{self.output_dir}'")

                    final_message = f"Processing complete. {volume_adj_summary}\nSuccessfully repacked into '{repacked_file_path}'.\nTemporary files cleaned up."
                    result_queue.put((final_message, True, False))
                except OSError as e:
                    print(f"Error cleaning up directory '{self.output_dir}': {e}", file=sys.stderr)
                    final_message = f"Processing complete. {volume_adj_summary}\nSuccessfully repacked into '{repacked_file_path}'.\n*Warning: Failed to clean up temporary directory '{self.output_dir}'.*"
                    result_queue.put((final_message, True, True))

            else:
                print("DEBUG: repack_pkr returned False or failed")
                raise RuntimeError(f"Repacking failed. Check console output for details. Temporary directory '{self.output_dir}' was not cleaned up.")

        except Exception as e:
            print("DEBUG: Exception caught in processing_worker")
            error_msg = f"An error occurred: {e}"
            print(error_msg, file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
            if 'repack_pkr' in locals() and not repack_success:
                 error_msg += f"\nRepacking to '{repacked_file_path}' may have failed."
            error_msg += f"\nTemporary directory '{self.output_dir}' may not have been cleaned up."
            result_queue.put((error_msg, True, True))


if __name__ == "__main__":
    try:
        import numpy
    except ImportError:
        root_check = tk.Tk()
        root_check.withdraw()
        messagebox.showerror("Dependency Error", "Required library 'numpy' is not installed.\nPlease install it using: pip install numpy")
        root_check.destroy()
        sys.exit(1)

    root = tk.Tk()
    app = PKRVolumeAdjusterApp(root)
    root.mainloop() 