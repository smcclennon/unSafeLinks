"""Windows utility to decode Microsoft SafeLinks URLs.

Monitors clipboard or accepts command line input to convert SafeLinks back to
original URLs.

Licensed under the MIT License (see LICENSE file)
Copyright (c) 2025 Shiraz McClennon
"""

# Using __future__.annotations allows modern type hint syntax (e.g. str | None)
# while maintaining compatibility with Python 3.7+, instead of requiring 3.10+
from __future__ import annotations

import ctypes
import ctypes.wintypes as w
import sys
import time
import urllib.parse

# Windows Clipboard Format Constants
# CF_UNICODETEXT (13): Windows clipboard format code for Unicode text data
CF_UNICODETEXT = 13

# Global Memory Allocation Flags
# GMEM_MOVEABLE (0x0002): Allocates moveable memory, required for clipboard
# operations
# GMEM_ZEROINIT (0x0040): Initialises memory to zero, kept for reference but
# unused
GMEM_MOVEABLE = 0x0002
GMEM_ZEROINIT = (
    0x0040  # Historical reference - not used in current implementation
)

# Load Windows API DLLs
# user32.dll: Contains clipboard and UI related functions
# kernel32.dll: Contains memory management functions
u32 = ctypes.WinDLL("user32")
k32 = ctypes.WinDLL("kernel32")

# Clipboard Access Functions
# OpenClipboard: Opens clipboard for examination/modification
# Parameters: HWND (window handle, None for current process)
# Returns: BOOL indicating success/failure
OpenClipboard = u32.OpenClipboard
OpenClipboard.argtypes = (w.HWND,)
OpenClipboard.restype = w.BOOL

# GetClipboardData: Retrieves data from clipboard in specified format
# Parameters: UINT (clipboard format identifier)
# Returns: HANDLE to clipboard data
GetClipboardData = u32.GetClipboardData
GetClipboardData.argtypes = (w.UINT,)
GetClipboardData.restype = w.HANDLE

# Memory Management Functions
# GlobalLock: Locks a global memory object and returns pointer to first byte
# Parameters: HGLOBAL (handle to global memory)
# Returns: LPVOID (pointer to memory)
# Note: Must be paired with GlobalUnlock to prevent memory leaks
GlobalLock = k32.GlobalLock
GlobalLock.argtypes = (w.HGLOBAL,)
GlobalLock.restype = w.LPVOID

# GlobalUnlock: Decrements lock count of global memory object
# Parameters: HGLOBAL (handle to global memory)
# Returns: BOOL indicating success/failure
# Note: Must be called once for each successful GlobalLock call
GlobalUnlock = k32.GlobalUnlock
GlobalUnlock.argtypes = (w.HGLOBAL,)
GlobalUnlock.restype = w.BOOL

# CloseClipboard: Closes clipboard and allows other processes to access it
# Parameters: None
# Returns: BOOL indicating success/failure
CloseClipboard = u32.CloseClipboard
CloseClipboard.argtypes = None
CloseClipboard.restype = w.BOOL

# GlobalAlloc: Allocates global memory with specified flags and size
# Parameters: UINT (allocation flags), SIZE_T (bytes to allocate)
# Returns: HGLOBAL (handle to allocated memory)
GlobalAlloc = k32.GlobalAlloc
GlobalAlloc.argtypes = [w.UINT, ctypes.c_size_t]
GlobalAlloc.restype = w.HGLOBAL

# GlobalFree: Frees specified global memory object
# Parameters: HGLOBAL (handle to global memory)
# Returns: HANDLE (NULL if successful, otherwise original handle)
GlobalFree = k32.GlobalFree
GlobalFree.argtypes = [w.HGLOBAL]
GlobalFree.restype = w.HANDLE

# SetClipboardData: Places data on clipboard in specified format
# Parameters: UINT (clipboard format), HANDLE (handle to data)
# Returns: HANDLE (handle to data on success, NULL on failure)
SetClipboardData = u32.SetClipboardData
SetClipboardData.argtypes = [w.UINT, w.HANDLE]
SetClipboardData.restype = w.HANDLE

# EmptyClipboard: Empties clipboard and frees handles to data in clipboard
# Parameters: None
# Returns: BOOL indicating success/failure
EmptyClipboard = u32.EmptyClipboard
EmptyClipboard.argtypes = []
EmptyClipboard.restype = w.BOOL


class ClipboardError(Exception):
    """Raised when clipboard operations fail."""

    EMPTY_FAILED = "Could not empty clipboard"
    SET_FAILED = "Could not set clipboard data"
    LOCKED = "Could not open clipboard - possibly locked by another process"


class MemoryAllocationError(Exception):
    """Raised when memory allocation or locking fails."""

    ALLOC_FAILED = "Could not allocate global memory"
    LOCK_FAILED = "Could not lock global memory"


def decode_safelink(safelink_url: str) -> str | None:
    """Decode a Microsoft SafeLink URL to its original form.

    Args:
        safelink_url (str): The SafeLink URL to decode (e.g.
            https://eur01.safelinks.protection.outlook.com/...)

    Returns:
        str or None: The decoded original URL if successful, None if the URL
            is not a valid SafeLink or lacks the 'url' parameter

    Example:
        >>> url = "https://eur01.safelinks.protection.outlook.com/?url=https%3A%2F%2Fexample.com"
        >>> decode_safelink(url)
        'https://example.com'

    """
    # Parse the URL and extract components
    parsed_url = urllib.parse.urlparse(safelink_url)

    # Extract and decode the 'url' parameter from query string
    query_params = urllib.parse.parse_qs(parsed_url.query)
    original_url = query_params.get("url", [None])[0]

    # Return decoded URL if found, None otherwise
    if original_url:
        return urllib.parse.unquote(original_url)
    return None


def get_clipboard_text() -> str:
    """Retrieve text from the Windows clipboard.

    Returns:
        str: The text content of the clipboard, or empty string if failed or if
            content is not text-based

    """
    text = ""
    try:
        if OpenClipboard(None):
            try:
                h_clip_mem = GetClipboardData(CF_UNICODETEXT)
                if h_clip_mem:  # Check if handle is valid
                    locked_mem = GlobalLock(h_clip_mem)
                    if locked_mem:  # Check if memory lock succeeded
                        try:
                            text = ctypes.wstring_at(locked_mem)
                        finally:
                            GlobalUnlock(h_clip_mem)
            finally:
                CloseClipboard()
    except (OSError, ValueError):
        # Handles access violations and other potential errors
        pass
    return text


def set_clipboard_text(text: str) -> None:
    """Set text to the Windows clipboard using Unicode format.

    Uses direct Windows API calls to handle memory allocation and clipboard
    operations. Memory management follows this sequence:
    1. Allocate global memory (GlobalAlloc)
    2. Lock memory for writing (GlobalLock)
    3. Copy data to memory (memmove)
    4. Unlock memory (GlobalUnlock)
    5. Set clipboard data - Windows takes ownership of memory
    6. Free memory if any steps fail (GlobalFree)

    Args:
        text (str): The text to be placed on the clipboard

    Raises:
        ClipboardError: If clipboard operations fail (opening, emptying,
            setting)
        MemoryAllocationError: If memory allocation or locking fails

    Note:
        The allocated memory is intentionally not freed after SetClipboardData
        succeeds, as Windows takes ownership of the memory at that point.

    """
    # Convert text to UTF-16 (Windows Unicode format) and ensure proper
    # null-termination
    text_bytes = (text + "\x00").encode("utf-16le")
    text_size = len(text_bytes)

    # Open the clipboard with retries in case another process has it locked
    for _ in range(5):
        if OpenClipboard(None):
            break
        time.sleep(0.1)
    else:
        raise ClipboardError(ClipboardError.LOCKED)

    try:
        # Empty the clipboard
        if not EmptyClipboard():
            raise ClipboardError(ClipboardError.EMPTY_FAILED)

        # Allocate global memory for the text
        h_global_mem = GlobalAlloc(GMEM_MOVEABLE, text_size)
        if not h_global_mem:
            raise MemoryAllocationError(MemoryAllocationError.ALLOC_FAILED)

        try:
            # Lock the memory block to get a pointer
            lp_mem = GlobalLock(h_global_mem)
            if not lp_mem:
                GlobalFree(h_global_mem)
                raise MemoryAllocationError(MemoryAllocationError.LOCK_FAILED)

            # Copy the text to the global memory
            ctypes.memmove(lp_mem, text_bytes, text_size)
            GlobalUnlock(h_global_mem)

            # Set the clipboard data
            if not SetClipboardData(CF_UNICODETEXT, h_global_mem):
                raise ClipboardError(ClipboardError.SET_FAILED)

            # Note: Windows takes ownership of the memory once SetClipboardData
            # succeeds
            h_global_mem = None
        finally:
            if h_global_mem:
                GlobalFree(h_global_mem)
    finally:
        CloseClipboard()


def run_service() -> None:
    """Run in continuous service mode, monitoring clipboard for SafeLinks URLs.

    When a SafeLink URL is detected, it immediately decodes and replaces it.
    The service runs indefinitely until interrupted by Ctrl+C.
    """
    print("SafeLinks decoder service started. Press Ctrl+C to stop.")
    last_content = ""

    try:
        while True:
            # Get current clipboard content
            current_content = get_clipboard_text()

            # Only process if content has changed and looks like a SafeLink
            if current_content != last_content and current_content.startswith(
                (
                    "https://gbr01.safelinks.protection.outlook.com/",
                    "https://eur01.safelinks.protection.outlook.com/",
                    "https://nam02.safelinks.protection.outlook.com/",
                ),
            ):
                decoded_url = decode_safelink(current_content)
                if decoded_url:
                    # Update clipboard with decoded URL
                    set_clipboard_text(decoded_url)
                    print(f"Decoded SafeLink to: {decoded_url}")

                last_content = decoded_url or current_content

            # Sleep briefly to prevent high CPU usage
            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\nSafeLinks decoder service stopped.")


def main() -> None:
    """Process SafeLinks from command line arguments or clipboard.

    Supports one-off URL decoding or continuous service mode.

    Arguments:
        --help: Show usage instructions
        --service: Run in continuous monitoring mode
        <url>: SafeLink URL to decode (optional)

    """
    if len(sys.argv) > 1:
        if sys.argv[1] == "--service":
            run_service()
            return

        if sys.argv[1] in ["--help", "-h", "/?"] or sys.argv[1][0] == "-":
            print(f"Usage: {sys.argv[0]} [OPTIONS] [URL]")
            print("\nDecodes Microsoft SafeLinks URLs to their original form.")
            print("\nOptions:")
            print(
                "  --service   Watch the clipboard and automatically replace "
                "SafeLinks with the original URL",
            )
            print("  --help      Show this help message")
            print("\nArguments:")
            print(
                "  URL         SafeLink to decode (optional, defaults to "
                "clipboard content)",
            )
            return

        safelink_url = sys.argv[1]
    else:
        safelink_url = get_clipboard_text()

    decoded_url = decode_safelink(safelink_url)

    if decoded_url:
        print(decoded_url)
        set_clipboard_text(decoded_url)
    else:
        print(
            "No valid SafeLink URL found. Use --help for usage instructions.",
        )


if __name__ == "__main__":
    main()
