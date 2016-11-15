import sys
import mplayer
import time

music_file = sys.argv[1]
p = mplayer.Player()
p.loadfile(music_file)
p.time_pos = 40
print p.length
print p.paused
p.pause()
print p.paused
time.sleep(10)
