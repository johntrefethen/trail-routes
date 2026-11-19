import math


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the great-circle distance in metres between two (lat, lon) points."""
    R = 6_371_000.0  # Earth radius in metres
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def interpolate_points(coord_list: list[tuple], interval_m: float = 50) -> list[tuple]:
    """Yield (lat, lon) samples every *interval_m* metres along a polyline.

    The first and last points of the polyline are always included.
    """
    if not coord_list:
        return []

    result = [coord_list[0]]
    accumulator = 0.0

    for i in range(1, len(coord_list)):
        prev = coord_list[i - 1]
        curr = coord_list[i]
        seg_len = haversine_m(prev[0], prev[1], curr[0], curr[1])

        if seg_len == 0:
            continue

        # How far along this segment do we still need to travel before the next sample?
        remaining = interval_m - accumulator

        while remaining <= seg_len:
            frac = remaining / seg_len
            lat = prev[0] + frac * (curr[0] - prev[0])
            lon = prev[1] + frac * (curr[1] - prev[1])
            result.append((lat, lon))
            remaining += interval_m

        accumulator = seg_len - (remaining - interval_m)

    # Always include the final point (avoid duplicating if it was just added)
    if result[-1] != coord_list[-1]:
        result.append(coord_list[-1])

    return result
