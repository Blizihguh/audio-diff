from pydub import AudioSegment
from pydub.utils import mediainfo
from argparse import ArgumentParser
import logging

#TODO: Setting to only look at one sample in a stereo recording, should usually be fine and give ~2x speedup?
#TODO: Could be worth a setting to reduce sample rate for processing (eg throw out every other sample for ~2x speedup, with minor loss of precision when calculating ad timestamps)
#TODO: Most ads are going to be ~30 seconds, so it might be worth searching like 14-35 first and then doubling back to 0-14 before doing 35+
#TODO: Handle different sample rates (downmux? would this even work in practice?)
#TODO: Once the above is done, -cf flag should have a default of 0, for "use whichever has the higher bitrate"

def data_from_file(path):
	# Convert the file to an array of samples
	# Some quick calculations tell me that 3-hour-long file at 44.1kHz should fit into a python list even on 32 bit -- I'm not sure but we'll try
	audio = AudioSegment.from_file(path, format="mp3")
	samples = []

	if audio.channels == 1 or audio.channels == 2:
		# Unfortunately, just converting a dual-channel file to an array will serialize the two channels (eg [s1left, s1right, s2left, s2right, ... snleft, snright])
		samples = audio.get_array_of_samples()
	else:
		logging.error("Error: Number of audio channels is " + str(audio.channels) + ", not 1-2.")
		raise ValueError

	info = mediainfo(path)

	returnVals = {
		"samples": samples,
		"length": len(samples),
		"isMono": audio.channels == 1,
		"sampleRate": audio.frame_rate,
		"sampleWidth": audio.sample_width,
		"audioSegment": audio,
		"bitrate": info["bit_rate"],
		"tags": info["TAG"]
	}
	return returnVals

def sample_distance(offset_a, offset_b, sampA, sampB):
	return abs(sampA[offset_a] - sampB[offset_b])

def find_resync_offset(start_a, start_b, isMono, sampleRate, sampA, sampB):
	# If the two sync up again, then there must be an amount by which we can offset a, such that they will be synced again
	# We try every offset until we find that amount, alternating between positive and negative shifts, because we don't know which direction to go
	# If we assume that no ad spot will last more than 5 minutes, and that ads will be at least 5 minutes apart, we can check if they're synced 5 minutes from now
	check_idx = sampleRate*60*5
	offset = 0
	check_a = start_a + check_idx
	check_b = start_b + check_idx
	max_sample = len(sampB)
	while True:
		if check_a + offset >= max_sample:
			return None
		if sample_distance(check_a+offset, check_b, sampA, sampB) <= MAX_DIFFERENCE:
			# This appears to be a match; we'll compare the next 100 samples just to make sure
			match = True
			for i in range(100):
				if sample_distance(check_a+offset+i, check_b+i, sampA, sampB) > MAX_DIFFERENCE: # Encoding can seemingly cause very small differences in samples...
					match = False
					break
			if match:
				if not isMono and offset % 2 == 1:
					offset += 1
				return offset # We offset a by this much to resync
		
		offset = -offset
		if offset >= 0:
			offset += 1

def find_next_match(start_a, start_b, isMono, sampA, sampB):
	# Look for a period of 100 samples to be sure
	offset = 0
	length = 0
	while True:
		if sample_distance(start_a+offset, start_b+offset, sampA, sampB) > MAX_DIFFERENCE:
			length = 0
		else:
			length += 1
		if length >= 5000 and offset-500 > 0:
			if not isMono and offset % 2 == 1:
				offset += 1
			return offset-5000
		offset += 1

def find_ads(sampA, sampB, isMono, sampleRate):
	# We assume that sampA is the longer of the two files, if they're different sizes
	mismatch_regions = [] # Areas to cut from sampB
	pos_a = 0
	pos_b = 0
	end_of_file = len(sampB)

	while pos_b+1 <= end_of_file:
		if sample_distance(pos_a, pos_b, sampA, sampB) <= MAX_DIFFERENCE:
			if isMono or sample_distance(pos_a+1, pos_b+1, sampA, sampB) <= MAX_DIFFERENCE:
				pos_a += 1
				pos_b += 1
				continue # The two samples match, we're still synced
		# If we didn't continue, that means we desynced (ie, we hit an ad)
		logging.debug(f"Mismatch found at {sample_timestamp(pos_a)}/{sample_timestamp(pos_b)} (samples {pos_a}/{pos_b})")
		resync = find_resync_offset(pos_a, pos_b, isMono, sampleRate, sampA, sampB)
		if resync == None:
			logging.debug("End of file")
			mismatch_regions.append((pos_a, pos_b, None, None))
			return mismatch_regions

		offset = find_next_match(pos_a+resync, pos_b, isMono, sampA, sampB)
		if offset == None:
			logging.debug("End of file")
			mismatch_regions.append((pos_a, pos_b, None, None))
			return mismatch_regions

		logging.debug(f"...resynced after adjusting A by {resync} then offsetting both by {offset}")
		logging.debug(f"...to skip ad, advance A by {sample_timestamp(resync+offset, sampleRate, isMono)} and B by {sample_timestamp(offset, sampleRate, isMono)}")
		mismatch_regions.append((pos_a, pos_b, resync+offset, offset))
		pos_a += resync+offset+1
		pos_b += offset+1 
		if pos_a < 0 or pos_b < 0:
			logging.error("ERROR: Position out of bounds")
			raise ValueError

	return mismatch_regions

def sample_timestamp(pos, sampleRate=44100, isMono=False):
	return timestamp_from_seconds(seconds_at_sample(pos, sampleRate, isMono))

def seconds_at_sample(pos, sampleRate, isMono):
	# Get the time, in seconds, at a certain sample position
	if pos == None:
		return -1
	if isMono:
		return pos/sampleRate
	else:
		return pos/(2*sampleRate)

def timestamp_from_seconds(seconds):
	hours   = int(seconds//3600) 
	minutes = int(seconds//60) % 60 # I don't know why seconds // 60 % 60 is returning a float but it apparently is :|
	milis   = int(100*(seconds - int(seconds)))
	seconds = seconds % 60
	res = f"{minutes:02d}:{int(seconds):02d}"
	if hours > 0:
		res = f"{hours}:" + res
	if SHOW_MILLIS:
		res = res + f".{milis:02d}"
	return res

def get_audio_data(fileA, fileB):

	logging.disable(level=logging.DEBUG) # Supress subprocess call
	logging.info("Loading files...")
	a_data = data_from_file(fileA)
	logging.info(f"Loaded {fileA}")
	b_data = data_from_file(fileB)
	logging.info(f"Loaded {fileB}")
	logging.info("Searching...")
	logging.disable(logging.NOTSET)

	return (a_data, b_data)

def compare_files(dataA, dataB, filenameA, filenameB):
	if not dataA["isMono"] == dataB["isMono"]:
		logging.error("Error: One file is single-channel and one is dual-channel")
		raise ValueError

	if not dataA["sampleRate"] == dataB["sampleRate"]:
		logging.error("Error: Files have different sample rates")
		raise ValueError

	mismatches = find_ads(dataA["samples"], dataB["samples"], dataA["isMono"], dataA["sampleRate"])

	logging.info(f"A: {filenameA}")
	logging.info(f"B: {filenameB}")
	for m in mismatches:
		tA = timestamp_from_seconds(seconds_at_sample(m[0], dataA["sampleRate"], dataA["isMono"]))
		tB = timestamp_from_seconds(seconds_at_sample(m[1], dataA["sampleRate"], dataA["isMono"]))
		skipA = timestamp_from_seconds(seconds_at_sample(m[2], dataA["sampleRate"], dataA["isMono"]))
		skipB = timestamp_from_seconds(seconds_at_sample(m[3], dataA["sampleRate"], dataA["isMono"]))
		logging.info(f"Mismatch at {tA} in A, {tB} in B; resync by skipping {skipA} in A, {skipB} in B.")

	return mismatches

def generate_cut_lists(mismatches):
	"""
	Separate the mismatch table into two separate lists of sample regions to cut (one for each file)
	"""
	a_list = []
	b_list = []
	for m in mismatches:
		if m[2] == None:
			a_list.append((m[0], -1))
		else:
			a_list.append((m[0], m[0]+m[2]))
		if m[3] == None:
			b_list.append((m[1], -1))
		else:
			b_list.append((m[1], m[1]+m[3]))
	return (a_list, b_list)

def remove_samples_from_list(samples, cuts):
	for c in reversed(cuts):   # Iterate backwards to avoid changing timestamps before we get to them
		del samples[c[0]:c[1]] # Extremely rare keyword spotted in the wild!
	return

def samples_to_file(data, filename):
	logging.disable(level=logging.DEBUG) # Supress subprocess call

	segment = data["audioSegment"]._spawn(data["samples"])
	with open(filename, "wb") as f:
		segment.export(f, format="mp3", bitrate=data["bitrate"], tags=data["tags"])
	logging.disable(logging.NOTSET)
	logging.info("Saved recut audio to " + filename)

def handle_args():
	parser = ArgumentParser(prog="Audio-Diff", description="A tool for identifying and removing differences in matching audio files.", usage="audio-diff.py [options] file_1 file_2 [output_file]")

	# argparse makes all output lowercase by default, but that's hard to read, so let's make it look nice (and match the custom argument formatting)
	parser._actions[0].help = "Show this message and exit."
	parser._positionals.title = "Positional arguments"
	parser._optionals.title = "Options"

	parser.add_argument("file_1", help="The first file to compare.")
	parser.add_argument("file_2", help="The second file to compare.")
	parser.add_argument("output_file", nargs="?", help="If provided, the matching audio sections will be saved to an mp3 file with that filename.")
	parser.add_argument("-q", "--quiet", action="count", default=0, help="Reduce amount of output text. Use -q to only output after the files are processed, or -qq to hide all output except errors.")
	parser.add_argument("-m", "--max", action="store", default=1, help="Set the maximum difference between samples to accept before flagging them as different audio. Default is 1."),
	parser.add_argument("-ms", "--milliseconds", action="count", default=0, help="If provided, timestamps will show miliseconds.")
	parser.add_argument("-cf", "--cutfile", action="store", default=0, help="Specify which file to use when recutting, eg -cf 1 to use file 1. By default the first file is used.")
	args = parser.parse_args()

	if args.quiet == 1:
		verbosity = logging.INFO
	elif args.quiet >= 2:
		verbosity = logging.ERROR
	else:
		verbosity = logging.DEBUG

	if args.max != 1:
		try:
			max_diff = int(args.max)
		except:
			print(f"ERROR: Maximum sample difference should be a number (got {args.max}). Continuing with default of 1.")
			max_diff = 1
		if int(args.max) < 0:
			print("ERROR: Maximum sample difference cannot be less than 0.")
			max_diff = 1
	else:
		max_diff = 1

	if args.miliseconds >= 1:
		miliseconds = True
	else:
		miliseconds = False

	if args.cutfile == "1":
		cf = 1
	elif args.cutfile == "2":
		cf = 2
	else:
		cf = 1

	return (args.file_1, args.file_2, args.output_file, verbosity, max_diff, miliseconds, cf)

if __name__ == '__main__':
	(filenameA, filenameB, outputName, verbosity, max_diff, timestamps, cf) = handle_args()
	logging.basicConfig(format="%(message)s", level=verbosity)
	MAX_DIFFERENCE = max_diff
	SHOW_MILLIS = timestamps

	(data_a, data_b) = get_audio_data(filenameA, filenameB)
	mismatches = compare_files(data_a, data_b, filenameA, filenameB)
	if outputName != None:
		(cuts_a, cuts_b) = generate_cut_lists(mismatches)
		if cf == 1:
			remove_samples_from_list(data_a["samples"], cuts_a)
			samples_to_file(data_a, outputName)
		elif cf == 2:
			remove_samples_from_list(data_b["samples"], cuts_b)
			samples_to_file(data_b, outputName)

