# What is Audio Diff?
Audio Diff is a tool to find (mis)matched content from two mp3 files, akin to tools that do the same thing for text files ("diff"). Optionally, it will also create a new file, which contains only content that matches between the two files.

# How do I use Audio Diff?
Dependencies: [pydub](https://github.com/jiaaro/pydub) (`pip install pydub`)

Usage: `audio-diff.py [options] file_1 file_2 [output_file]`

Provide the two files you want to compare, and optionally, the filename for output. A number of command-line options are also supported:

`-q, --quiet` reduces the amount of console output. A single -q will suppress output until the files are fully compared; -qq will suppress all output apart from errors.

`-m, --max` can be used to change how much difference the program should tolerate between two samples before considering them to be different. By default this is 1, so an audio sample of 45 would be considered the same as an audio sample of 44 or 46. It's not recommended to change this, as many audio workflows can be expected to change samples by this much. A stricter setting may introduce false positives, where the program sees two files as different when the difference would be imperceptible to the human ear.

# Why is Audio Diff?
Have you ever been listening to a podcast, fully immersed, when this happened?
> "Most of the time, it was pretty slow going." *That's Bob McAllison, who spent thirty years as the head of the Blue Rock Police Department's homicide division.* "Not a lot happened 'round Blue Rock back in those days. Certainly not a lot of murders. When we got to the scene, poor Jim nearly vomitted -- it was gruesome stuff. And it never leaves you, seeing all those people. All those bits of people, chewed up. ... I still have nightmares." *Paypal makes it easy for you to pay all your pals! Whether you're at home or on the go, it's never been easier to split the bill!*

This is a solvable problem. It's solvable for the people whose job it is to produce podcasts (and ads for podcasts). But frequently, those people choose not to solve it. Thankfully, it's also a solvable problem for listeners.

In short: dynamic ads are advertisements that are automatically inserted into a podcast after it's been released. These have many qualities that make them appealing to podcast producers and advertisers: they can be updated to continue selling ad space on old content, and they can be changed depending on the user's region, and of course, they can leverage all of the tracking information that advertising companies keep on you. Unfortunately, the industry standard is to insert these ads basically randomly in the podcast audio, with little to no effort spent on ensuring the result is still listenable. Whereas radio and tv have had sponsor segues and planned ad breaks for as long as anyone can remember, podcasts typically don't anymore -- even though they used to! Depending on the subject matter of the podcast, this can range from frustrating to downright offensive.

Thankfully, the very nature of dynamic ads provides their undoing. Downloading a podcast is extremely easy, and because the goal is to serve different ads to different listeners, it's pretty easy to get two copies of a podcast episode that differ only by the ads contained within. That's where Audio Diff comes in.
