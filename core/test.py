import sys
import lxml.html as p

from transcoder import Transcoder
import transcode.utils.misc as misc

url = sys.argv[1]

dom = misc.load_dom(url)

if dom is None:
    print "dom tree can't be loaded"
else:
    transcoder = Transcoder()
    result_dom = transcoder.transcode(url, dom)
    new_html = p.tostring(result_dom)
    with open(sys.argv[2], "w") as f:
        f.write(new_html)
    print "finished"
