this was supposed to be my submission for cal hacks. the only problem is that i didn't finish it. what was supposed to take 3 days has turned into well over a week of development, with no end in sight

anyway, i'm leaving this repository public as a proof of concept. it is extremely unfinished, broken in ways i haven't discovered yet, and generally a work in progress. make of that what you will

i'm not even going to explain what this is yet. you'll figure it out. or you won't

it shall be updated. eventually

kisses

## Install and launch

Windows PowerShell, with Git and Python 3.12 or newer installed:

```powershell
git clone https://github.com/clarezahermetica/doxa.git
cd doxa
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\doxa.exe
```

Choose or create a workspace when prompted. Press F1 for help or Ctrl+P for commands.
Start with an offline synthetic experiment; live inference requires separate connection
configuration and explicit authorization. No binary download is provided with this update.

## GPT-written note

GPT wrote the installation instructions and this notice at the author's request while
development continues. They will be replaced with a human-written README. The personal
introduction above is the author's own text.

This proof of concept has not yet been tested through independent real-world use or
live-provider acceptance. Automated checks do not guarantee reliability. It may be
incomplete, contain undiscovered bugs, or fail unexpectedly.
