'''
Usage:
  ms_plot <metadata-url> [--limit=<N>] [--cert=<file>]

'''

from docopt import docopt
import requests
import matplotlib
from consts import ET_TO_YLABEL, ET_TO_TRANS
from datetime import datetime

# http://matplotlib.org/
matplotlib.use('GTKAgg') # do this before importing pylab
import matplotlib.pyplot as plt
import time

def setup_figure(fig):
    fig.subplotpars.hspace = 0.5
    fig.subplotpars.wspace = 0.16
    fig.subplotpars.left = 0.06
    fig.subplotpars.right = .96
    fig.subplotpars.top = .96
    fig.subplotpars.bottom = .04
    return fig

mds = []
data = {}
axes = {}
AXES = {}
ms_url = None
cert_key = None
limit = 100
fig = setup_figure(plt.figure())
YTICKNUM = 6
XTICKNUM = 4

def main(arguments):
    global cert_key
    global mds
    global limit
    global ms_url

    if arguments['--limit']:
        limit = arguments['--limit']

    if arguments['--cert']:
        cert_key = arguments['--cert']

    r = None
    try:
        r = requests.get(arguments['<metadata-url>'], cert=cert_key, verify=False)
    except Exception as e:
        print "Could not retrieve metadata: %s" % e
        exit(1)
    
    if r:
        # can push any number of metadata object into mds array
        # to plot them all at once
        mds = [r.json()]
        meas_url = mds[0]["parameters"]["measurement"]["href"]
        m = requests.get(meas_url, cert=cert_key, verify=False)
        meas = m.json()
        ms_url = meas["configuration"]["ms_url"]
        plot_all()
    else:
        print "No data returned"
        exit(1)

def plot_all():
    global mds
    plotnum = 0
    numrows = len(mds)/2
    if len(mds)%2==1:
        numrows += 1
    for md in mds:
        data[md["id"]] = {}
        plotnum += 1
        tss, vals = get_data(md, "?limit="+str(limit))
        vals = map(ET_TO_TRANS[md["eventType"]], vals)
        xticks = get_ticks(tss, XTICKNUM)
        ax = fig.add_subplot(numrows, 1, plotnum,
                             xticklabels = get_ts_labels(xticks),
                             xticks=xticks,
                             ylabel = ET_TO_YLABEL[md["eventType"]])
        ax.set_autoscale_on(True)
        ax.autoscale_view(tight=False)
        line, = ax.plot(tss, vals, '-bo')
        AXES[md["id"]] = ax
        axes[md["id"]] = line
        td = data[md["id"]]
        td["tss"] = tss
        td["vals"] = vals
        ax.set_title(':'.join(md["eventType"].split(':')[-3:]))
    import gobject
    gobject.timeout_add(2000, animate)
    plt.show()


def animate():
    plotnum = 0
    for md in mds:
        plotnum += 1
        td = data[md["id"]]
        tss = td["tss"]
        vals = td["vals"]
        xtraq = "?ts=gt=%d"%(int(tss[-1]))
        newtss, newvals = get_data(md, xtraq)
        newvals = map(ET_TO_TRANS[md["eventType"]], newvals)
        tss.extend(newtss)
        vals.extend(newvals)
        ax = AXES[md["id"]]
        xticks = get_ticks(tss, XTICKNUM)
        ax.set_xticks(xticks)
        ax.set_xticklabels(get_ts_labels(xticks))
        ax.plot(tss, vals, '-bo')
    fig.canvas.draw()
    return True

def get_data(metadata, xtraq=""):
    r = requests.get(ms_url + "/data/" + metadata["id"] + xtraq, cert=cert_key, verify=False)
    return extract_data(r)

def get_ticks(xdata, num_ticks):
    sd = sorted(xdata)
    top = float(sd[-1])
    bot = float(sd[0])
    skip = (top-bot)/float(num_ticks)
    if skip==0:
        top *= 1.1
        bot *= 0.9
        skip = (top-bot)/float(num_ticks)
    tick = bot
    ticks = []
    while tick < top:
        ticks.append(tick)
        tick += skip
    return ticks

def get_tick_labels(ticks):
    t =  sorted(ticks)
    return t

def extract_data(r):
    if not r:
        return ([], [])
    tss = [ r.json()[i]["ts"] for i in range(len(r.json())-1, -1, -1) ]
    vals = [ float(r.json()[i]["value"]) for i in range(len(r.json())-1, -1, -1) ]
    return tss, vals

def get_ts_labels(tss):
    labels = tss[:]
    for i in range(len(labels)):
        labels[i] = datetime.fromtimestamp(labels[i]/1000000).strftime('%H:%M:%S')
    return labels


if __name__ == '__main__':
    arguments = docopt(__doc__, version = 'ms_plot 0.1')
    main(arguments)
