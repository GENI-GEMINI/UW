ET_TO_YLABEL = {
    "ps:tools:blipp:linux:cpu:utilization:user":"fraction",
    "ps:tools:blipp:linux:cpu:utilization:system":"fraction",
    "ps:tools:blipp:linux:cpu:utilization:nice":"fraction",
    "ps:tools:blipp:linux:cpu:utilization:iowait":"fraction",
    "ps:tools:blipp:linux:cpu:utilization:hwirq":"fraction",
    "ps:tools:blipp:linux:cpu:utilization:swirq":"fraction",
    "ps:tools:blipp:linux:cpu:utilization:steal":"fraction",
    "ps:tools:blipp:linux:cpu:utilization:guest":"fraction",
    "ps:tools:blipp:linux:cpu:utilization:idle":"fraction",
    "ps:tools:blipp:linux:cpu:load:onemin":"load",
    "ps:tools:blipp:linux:cpu:load:fivemin":"load",
    "ps:tools:blipp:linux:cpu:load:fifteenmin":"load",
    "ps:tools:blipp:linux:network:ip:utilization:packets:in":"packets",
    "ps:tools:blipp:linux:network:ip:utilization:packets:out":"packets",
    "ps:tools:blipp:linux:network:utilization:bytes:in":"Mbytes",
    "ps:tools:blipp:linux:network:utilization:bytes:out":"Mbytes",
    "ps:tools:blipp:linux:network:ip:utilization:errors":"errors",
    "ps:tools:blipp:linux:network:ip:utilization:drops":"drops",
    "ps:tools:blipp:linux:network:tcp:utilization:segments:in":"segments",
    "ps:tools:blipp:linux:network:tcp:utilization:segments:out":"segments",
    "ps:tools:blipp:linux:network:tcp:utilization:retrans":"segments",
    "ps:tools:blipp:linux:network:udp:utilization:datagrams:in":"datagrams",
    "ps:tools:blipp:linux:network:udp:utilization:datagrams:out":"datagrams",
    "ps:tools:blipp:linux:memory:utilization:free":"GB",
    "ps:tools:blipp:linux:memory:utilization:used":"GB",
    "ps:tools:blipp:linux:memory:utilization:buffer":"GB",
    "ps:tools:blipp:linux:memory:utilization:cache":"GB",
    "ps:tools:blipp:linux:memory:utilization:kernel":"GB",
    "ps:tools:blipp:linux:net:ping:ttl":"seconds",
    "ps:tools:blipp:linux:net:ping:rtt":"ms",
    "ps:tools:blipp:linux:net:iperf:bandwidth":"Mbytes/s"
    }

def kb_to_gb(num):
    return float(num)/(1024.*1024.)

def nothing(num):
    return num

def b_to_mb(num):
    return float(num)/(1024.*1024.)

ET_TO_TRANS = {
    "ps:tools:blipp:linux:cpu:utilization:user":nothing,
    "ps:tools:blipp:linux:cpu:utilization:system":nothing,
    "ps:tools:blipp:linux:cpu:utilization:nice":nothing,
    "ps:tools:blipp:linux:cpu:utilization:iowait":nothing,
    "ps:tools:blipp:linux:cpu:utilization:hwirq":nothing,
    "ps:tools:blipp:linux:cpu:utilization:swirq":nothing,
    "ps:tools:blipp:linux:cpu:utilization:steal":nothing,
    "ps:tools:blipp:linux:cpu:utilization:guest":nothing,
    "ps:tools:blipp:linux:cpu:utilization:idle":nothing,
    "ps:tools:blipp:linux:cpu:load:onemin":nothing,
    "ps:tools:blipp:linux:cpu:load:fivemin":nothing,
    "ps:tools:blipp:linux:cpu:load:fifteenmin":nothing,
    "ps:tools:blipp:linux:network:ip:utilization:packets:in":nothing,
    "ps:tools:blipp:linux:network:ip:utilization:packets:out":nothing,
    "ps:tools:blipp:linux:network:utilization:bytes:in":b_to_mb,
    "ps:tools:blipp:linux:network:utilization:bytes:out":b_to_mb,
    "ps:tools:blipp:linux:network:ip:utilization:errors":nothing,
    "ps:tools:blipp:linux:network:ip:utilization:drops":nothing,
    "ps:tools:blipp:linux:network:tcp:utilization:segments:in":nothing,
    "ps:tools:blipp:linux:network:tcp:utilization:segments:out":nothing,
    "ps:tools:blipp:linux:network:tcp:utilization:retrans":nothing,
    "ps:tools:blipp:linux:network:udp:utilization:datagrams:in":nothing,
    "ps:tools:blipp:linux:network:udp:utilization:datagrams:out":nothing,
    "ps:tools:blipp:linux:memory:utilization:free":kb_to_gb,
    "ps:tools:blipp:linux:memory:utilization:used":kb_to_gb,
    "ps:tools:blipp:linux:memory:utilization:buffer":kb_to_gb,
    "ps:tools:blipp:linux:memory:utilization:cache":kb_to_gb,
    "ps:tools:blipp:linux:memory:utilization:kernel":kb_to_gb,
    "ps:tools:blipp:linux:net:ping:ttl":nothing,
    "ps:tools:blipp:linux:net:ping:rtt":nothing,
    "ps:tools:blipp:linux:net:iperf:bandwidth":b_to_mb
    }
