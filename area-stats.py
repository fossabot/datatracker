#!/usr/bin/env python

import datetime
import os

os.environ["DJANGO_SETTINGS_MODULE"] = "ietf.settings"

import django

django.setup()

from django.db.models import Sum, Q
from django.utils import timezone

from ietf.doc.models import Document
from ietf.group.models import Group

import pandas as pd
import plotly.express as px
import plotly.io as pio
import plotly.graph_objects as go

pio.kaleido.scope.mathjax = None


def fmt_acronym(group):
    return group.acronym if group.state.slug == "active" else f"({group.acronym})"


def mk_row(name, docs, pages, parent):
    return pd.DataFrame.from_records(
        [(name, docs, pages, parent)],
        columns=["name", "docs", "pages", "parent"],
    )


def mk_row_group(group, group_docs):
    return mk_row(
        fmt_acronym(group),
        group_docs.count() or 0,
        group_docs.aggregate(Sum("pages"))["pages__sum"] or 0,
        fmt_acronym(group.parent),
    )


when = timezone.now() - datetime.timedelta(days=3 * 365)
docs = (
    Document.objects.filter(type="draft", stream="ietf")
    .filter(
        Q(docevent__newrevisiondocevent__time__gte=when)
        | Q(docevent__type="published_rfc", docevent__time__gte=when)
    )
    .exclude(states__type="draft", states__slug="repl")
    .distinct()
)


df = pd.DataFrame()
for a in Group.objects.filter(type="area"):
    area_docs = docs.filter(group__parent=a).exclude(group__acronym="none")
    if not area_docs:
        continue

    df = pd.concat([df, mk_row_group(a, area_docs)], ignore_index=True)

    for wg in Group.objects.filter(type="wg", parent=a):
        wg_docs = area_docs.filter(group=wg)

        if not wg_docs:
            continue

        df = pd.concat([df, mk_row_group(wg, wg_docs)], ignore_index=True)

        for doc in wg_docs:
            name = (
                f"rfc{doc.rfc_number()}"
                if doc.rfc_number()
                else doc.name  # .replace("draft-", "")
            )
            # print(wg.parent.acronym, wg.acronym, name, doc.get_state_slug())
            df = pd.concat(
                [df, mk_row(name, 1, doc.pages, fmt_acronym(wg))], ignore_index=True
            )

        area_docs = area_docs.exclude(group=wg)

print(df.to_string())


def sunburst(label):
    fig = px.sunburst(
        df.replace("iesg", label),
        names="name",
        values=label,
        parents="parent",
        branchvalues="total",
    )
    fig.update_layout(margin=dict(t=0, l=0, r=0, b=0))
    # fig.update_traces(insidetextorientation="radial")
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
        if row.empty:
            continue
        old_area = row["parent"].iloc[0]
        value = row[label].iloc[0]
        sources.append(key[old_area])
        if new_area not in new_key:
            continue
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
    fig.update_layout(margin=dict(t=0, l=0, r=0, b=0))
    fig.write_image(f"area-{label}-sankey.pdf")


sunburst("docs")
sunburst("pages")

# dict format: "group -> new area"
changes = {
    # My proposal
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
    # Martin's proposal
    # "alto": "ops",
    # "dtn": "int",
    # "ippm": "ops",
    # "masque": "int",
    # "nfsv4": "art",
    # # "quic": "int",
    # # "rmcat": "int",
    # # "taps": "int",
    # # "tcpm": "int",
    # # "tsvwg ": "int",
}

sankey("docs", changes)
sankey("pages", changes)
