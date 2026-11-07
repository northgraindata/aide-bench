import csv
import sys

BANDS = {b: "%d-%d" % (b, b + 4) for b in range(15, 85, 5)}


def band_of(age):
    return age / 5 * 5


def main(path):
    counts = {}
    rows = list(csv.DictReader(open(path)))
    print("loaded %d customers" % len(rows))
    assigned = 0
    for row in rows:
        label = BANDS.get(band_of(int(row["age"])))
        if label is None:
            continue
        counts[label] = counts.get(label, 0) + 1
        assigned += 1
    print("assigned %d customers to bands" % assigned)
    return counts


if __name__ == "__main__":
    main(sys.argv[1])
