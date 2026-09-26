"""One-to-one association of refreshed person boxes with visible visits."""


def overlap(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    intersection = max(0, min(ax + aw, bx + bw) - max(ax, bx)) * max(0, min(ay + ah, by + bh) - max(ay, by))
    return intersection / max(1, aw * ah + bw * bh - intersection)


def match_score(a, b):
    iou = overlap(a, b)
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    distance = ((ax + aw / 2 - bx - bw / 2) ** 2 + (ay + ah / 2 - by - bh / 2) ** 2) ** .5
    scale = max(aw, ah, bw, bh, 1)
    if iou < .08 and distance > .65 * scale:
        return None
    return iou + max(0, 1 - distance / scale) * .25


def reconcile_tracks(current, detected, now, hold_seconds=3.0):
    old = [track for track in current if now - track['confirmed'] <= hold_seconds]
    fresh = [dict(track) for track in detected]
    pairs = []
    for old_index, track in enumerate(old):
        for new_index, candidate in enumerate(fresh):
            score = match_score(track['box'], candidate['box'])
            if score is not None:
                pairs.append((score, old_index, new_index))
    used_old, used_new = set(), set()
    for _, old_index, new_index in sorted(pairs, reverse=True):
        if old_index in used_old or new_index in used_new:
            continue
        for key in ('visit_id', 'track_id'):
            if key in old[old_index]:
                fresh[new_index][key] = old[old_index][key]
        used_old.add(old_index)
        used_new.add(new_index)
    retained = [track for index, track in enumerate(old) if index not in used_old and all(overlap(track['box'], item['box']) < .3 for item in fresh)]
    return fresh + retained
