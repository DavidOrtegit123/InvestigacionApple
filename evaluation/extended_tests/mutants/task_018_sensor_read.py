# Wrong on purpose: takes the middle reading in call order instead of the
# median (the readings are never sorted).
def read_celsius(sensor):
    readings = [sensor.read_raw() for _ in range(3)]
    return float(round((readings[1] - sensor.offset) * sensor.gain / 100, 1))
