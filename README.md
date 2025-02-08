# unSafeLinks

Automatically decode Microsoft SafeLinks URLs and replace them in your Windows clipboard.

## Overview

unSafeLinks is a Windows utility that decodes Microsoft SafeLinks URLs back to their original form. It can operate in two modes:
- One-off conversion of a single URL
- Continuous monitoring service that automatically converts SafeLinks in your clipboard

## Features

- Decodes SafeLinks from multiple Microsoft domains (gbr01, eur01, nam02)
- No configuration required
- Lightweight clipboard monitoring
- Command-line interface
- Automatic clipboard updates with decoded URLs
- Safe memory handling using Windows API
- Type-safe implementation with Python type hints
- No external dependencies - works with standard Python 3.7+ installation

## Installation

1. **Download the script directly**
   - Right-click [this link](https://raw.githubusercontent.com/smcclennon/unSafeLinks/refs/heads/main/src/unSafeLinks.py) and select "Save link as..." to download unSafeLinks.py
   - Or if you have curl installed:
     ```bash
     curl -O https://raw.githubusercontent.com/smcclennon/unSafeLinks/refs/heads/main/src/unSafeLinks.py
     ```

## Usage

### One-time Conversion

1. **From Clipboard**
   - Double-click `unSafeLinks.py`, or
   - Run in Command Prompt:
     ```cmd
     python unSafeLinks.py
     ```
   This will decode any SafeLink URL in your clipboard and replace it with the original URL.

2. **Specific URL**
   ```bash
   python unSafeLinks.py "https://eur01.safelinks.protection.outlook.com/..."
   ```
   This will decode the provided SafeLink URL and copy the result to your clipboard.

### Continuous Monitoring

```cmd
python unSafeLinks.py --service
```
This will:
- Watch your clipboard for SafeLinks URLs
- Automatically decode and replace them
- Display decoded URLs in the console
- Continue running until the process is killed

Example output:
```
$ python unSafeLinks.py --service
SafeLinks decoder service started. Press Ctrl+C to stop.
Decoded SafeLink to: https://duckduckgo.com
Decoded SafeLink to: https://peps.python.org/pep-0563/#abstract
```

## Requirements

- Windows operating system
- Python 3.7 or higher

## License
This project is licensed under the [MIT License](LICENSE).
