from datetime import datetime

slots = {

"S1":"08:00-09:00",
"S2":"09:00-10:00",
"BREAK":"10:00-10:20",
"S3":"10:20-11:20",
"S4":"11:20-12:20",
"LUNCH":"12:20-01:10",
"S5":"01:10-02:10",
"S6":"02:10-03:10",
"S7":"03:10-04:10"

}

def get_current_slot():

    now = datetime.now()
    current = now.strftime("%H:%M")

    for slot,time_range in slots.items():

        start,end = time_range.split("-")

        if start <= current <= end:

            return slot

    return "Break"
