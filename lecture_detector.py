<<<<<<< HEAD
from datetime import datetime
from time_slots import get_current_slot
from timetable_data import timetable


def get_current_lecture():

    day = datetime.now().strftime("%a")

    slot = get_current_slot()

    if slot == "Break":
        return "Break Time"

    return timetable.get(day,{}).get(slot,"Free Lecture")
=======
from datetime import datetime
from time_slots import get_current_slot
from timetable_data import timetable


def get_current_lecture():

    day = datetime.now().strftime("%a")

    slot = get_current_slot()

    if slot == "Break":
        return "Break Time"

    return timetable.get(day,{}).get(slot,"Free Lecture")
>>>>>>> 81bf992d76a815cbb279ad7749e4cf614edd9542
