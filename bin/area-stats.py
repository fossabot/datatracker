#!/usr/bin/env python

import datetime
import json
import os

os.environ["DJANGO_SETTINGS_MODULE"] = "ietf.settings"

import django

django.setup()

from django.db.models import Sum
from django.utils import timezone

from ietf.doc.models import Document
from ietf.group.models import Group

import numpy as np
import matplotlib.pyplot as plt


def doc_details(doc):
    return (
        doc.name,
        doc.docevent_set.filter(type="iesg_approved")
        .latest("time")
        .time.strftime("%F"),
    )


docs = Document.objects.filter(
    docevent__type="iesg_approved",
    docevent__time__gte=timezone.now() - datetime.timedelta(days=3 * 365),
)

stats = {}
for a in Group.objects.filter(type="area"):
    area_docs = docs.filter(group__parent=a)
    if not area_docs:
        continue

    stats[a.acronym] = {
        "docs": area_docs.count(),
        "pages": area_docs.aggregate(Sum("pages"))["pages__sum"],
        "wgs": {},
    }

    for wg in Group.objects.filter(type="wg", parent=a, state="active").order_by(
        "acronym"
    ):
        wg_docs = area_docs.filter(group=wg)

        stats[a.acronym]["wgs"][wg.acronym] = {
            "docs": wg_docs.count(),
            "pages": wg_docs.aggregate(Sum("pages"))["pages__sum"],
            "details": [doc_details(d) for d in wg_docs.order_by("name")],
        }

        area_docs = area_docs.exclude(group=wg)

    stats[a.acronym]["other"] = [doc_details(d) for d in area_docs.order_by("name")]


def plot(label):
    fig, ax = plt.subplots()
    data = [stats[a][label] for a in stats.keys()]

    def autopct(pct):
        absolute = int(np.round(pct / 100.0 * np.sum(data)))
        return "{:d} {:s}\n({:.0f}%)".format(absolute, label, pct)

    ax.pie(data, labels=stats.keys(), autopct=lambda pct: autopct(pct))
    ax.axis("equal")
    ax.set_title(f"{label} per area")
    plt.savefig(f"area-{label}.png", bbox_inches="tight", pad_inches=0)


print(json.dumps(stats, indent=4))

plot("docs")
plot("pages")
