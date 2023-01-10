#!/usr/bin/env python

import datetime
import os

os.environ["DJANGO_SETTINGS_MODULE"] = "ietf.settings"

import django

django.setup()

from django.db.models import Sum
from django.utils import timezone

from ietf.doc.models import Document
from ietf.group.models import Group

import pandas as pd
import plotly.express as px
import plotly.io as pio
import plotly.graph_objects as go

pio.kaleido.scope.mathjax = None


# def doc_details(doc):
#     return (
#         doc.name,
#         doc.docevent_set.filter(type="iesg_approved")
#         .latest("time")
#         .time.strftime("%F"),
#     )


def mk_row(group, group_docs):
    return pd.DataFrame.from_records(
        [
            (
                group.acronym,
                group_docs.count() or 0,
                group_docs.aggregate(Sum("pages"))["pages__sum"] or 0,
                group.parent.acronym,
            ),
        ],
        columns=["name", "docs", "pages", "parent"],
    )


docs = Document.objects.filter(
    docevent__type="iesg_approved",
    docevent__time__gte=timezone.now() - datetime.timedelta(days=3 * 365),
)

df = pd.DataFrame()
for a in Group.objects.filter(type="area"):
    area_docs = docs.filter(group__parent=a)
    if not area_docs:
        continue

    df = pd.concat([df, mk_row(a, area_docs)], ignore_index=True)

    for wg in Group.objects.filter(type="wg", parent=a, state="active"):
        wg_docs = area_docs.filter(group=wg)
        df = pd.concat([df, mk_row(wg, wg_docs)], ignore_index=True)

        area_docs = area_docs.exclude(group=wg)


def sunburst(label):
    fig = px.sunburst(
        df.replace("iesg", label),
        names="name",
        values=label,
        parents="parent",
        branchvalues="total",
    )
    fig.update_layout(margin=dict(t=0, l=0, r=0, b=0))
    # fig.update_traces(sort=False)
    # fig.update_traces(textinfo="label+percent parent")
    fig.write_image(f"area-{label}.pdf")


def sankey(label, changes):
    areas = df[df["parent"] == "iesg"]

    key = {y: x for x, y in enumerate(areas["name"])}
    new_key = {y: x + len(key) for x, y in enumerate(areas["name"])}

    sources = []
    targets = []
    values = []
    link_labels = []
    deltas = [0 for _ in key]
    for group, new_area in changes.items():
        row = df[df["name"] == group]
        old_area = row["parent"].iloc[0]
        value = row[label].iloc[0]
        sources.append(key[old_area])
        targets.append(new_key[new_area])
        values.append(value)
        deltas[key[old_area]] += value
        link_labels.append(row["name"].iloc[0])

    for _, area in areas.iterrows():
        name = area["name"]
        sources.append(key[name])
        targets.append(new_key[name])
        values.append(area[label] - deltas[key[name]])

    node_labels = list(key.keys()) + list(key.keys())
    node_colors = px.colors.qualitative.Plotly[: len(key)]
    node_colors.extend(node_colors)

    fig = go.Figure(
        data=[
            go.Sankey(
                node=dict(
                    label=node_labels,
                    color=node_colors,
                ),
                link=dict(
                    source=sources,
                    target=targets,
                    value=values,
                    label=link_labels,
                ),
            )
        ]
    )
    print(fig)
    fig.update_layout(margin=dict(t=0, l=0, r=0, b=0))
    fig.write_image(f"area-{label}-sankey.pdf")


sunburst("docs")
sunburst("pages")

# dict format: "group -> new area"
changes = {
    "ippm": "int",
    "bmwg": "int",
    "detnet": "int",
    "lisp": "int",
    "nvo3": "int",
    "raw": "int",
    "httpbis": "tsv",
    "httpapi": "tsv",
    "webtrans": "tsv",
    "core": "tsv",
}

sankey("docs", changes)
sankey("pages", changes)
