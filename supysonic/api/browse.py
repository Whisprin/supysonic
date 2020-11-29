# This file is part of Supysonic.
# Supysonic is a Python implementation of the Subsonic server API.
#
# Copyright (C) 2013-2020 Alban 'spl0k' Féron
#
# Distributed under terms of the GNU AGPLv3 license.

import re
import string

from flask import current_app, request
from pony.orm import ObjectNotFound, select, count

from ..db import Folder, Artist, Album, Track

from . import api, get_entity, get_entity_id


@api.route("/getMusicFolders.view", methods=["GET", "POST"])
def list_folders():
    return request.formatter(
        "musicFolders",
        dict(
            musicFolder=[
                dict(id=str(f.id), name=f.name)
                for f in Folder.select(lambda f: f.root).order_by(Folder.name)
            ]
        ),
    )


def build_ignored_articles_pattern():
    articles = current_app.config["WEBAPP"]["index_ignored_prefixes"]
    if articles is None:
        return None

    articles = articles.split()
    if not articles:
        return None

    return r"^(" + r" |".join(re.escape(a) for a in articles) + r" )"


def ignored_articles_str():
    articles = current_app.config["WEBAPP"]["index_ignored_prefixes"]
    if articles is None:
        return ""

    return " ".join(articles.split())


@api.route("/getIndexes.view", methods=["GET", "POST"])
def list_indexes():
    musicFolderId = request.values.get("musicFolderId")
    ifModifiedSince = request.values.get("ifModifiedSince")
    if ifModifiedSince:
        ifModifiedSince = int(ifModifiedSince) / 1000

    if musicFolderId is None:
        folders = Folder.select(lambda f: f.root)[:]
    else:
        mfid = get_entity_id(Folder, musicFolderId)
        folder = Folder[mfid]
        if not folder.root:
            raise ObjectNotFound(Folder, mfid)

        folders = [folder]

    last_modif = max(map(lambda f: f.last_scan, folders))
    if ifModifiedSince is not None and last_modif < ifModifiedSince:
        return request.formatter(
            "indexes",
            dict(
                lastModified=last_modif * 1000, ignoredArticles=ignored_articles_str()
            ),
        )

    # The XSD lies, we don't return artists but a directory structure
    artists = []
    children = []
    for f in folders:
        artists += f.children.select()[:]
        children += f.tracks.select()[:]

    indexes = dict()
    pattern = build_ignored_articles_pattern()
    for artist in artists:
        name = artist.name
        if pattern:
            name = re.sub(pattern, "", name, flags=re.I)
        index = name[0].upper()
        if index in string.digits:
            index = "#"
        elif index not in string.ascii_letters:
            index = "?"

        if index not in indexes:
            indexes[index] = []

        indexes[index].append((artist, name))

    return request.formatter(
        "indexes",
        dict(
            lastModified=last_modif * 1000,
            ignoredArticles=ignored_articles_str(),
            index=[
                dict(
                    name=k,
                    artist=[
                        a.as_subsonic_artist(request.user)
                        for a, _ in sorted(v, key=lambda t: t[1].lower())
                    ],
                )
                for k, v in sorted(indexes.items())
            ],
            child=[
                c.as_subsonic_child(request.user, request.client)
                for c in sorted(children, key=lambda t: t.sort_key())
            ],
        ),
    )


@api.route("/getMusicDirectory.view", methods=["GET", "POST"])
def show_directory():
    res = get_entity(Folder)
    return request.formatter(
        "directory", res.as_subsonic_directory(request.user, request.client)
    )


@api.route("/getGenres.view", methods=["GET", "POST"])
def list_genres():
    return request.formatter(
        "genres",
        dict(
            genre=[
                dict(value=genre, songCount=sc, albumCount=ac)
                for genre, sc, ac in select(
                    (t.genre, count(), count(t.album)) for t in Track if t.genre
                )
            ]
        ),
    )


@api.route("/getArtists.view", methods=["GET", "POST"])
def list_artists():
    # According to the API page, there are no parameters?
    indexes = dict()
    pattern = build_ignored_articles_pattern()
    for artist in Artist.select():
        name = artist.name or "?"
        if pattern:
            name = re.sub(pattern, "", name, flags=re.I)
        index = name[0].upper()
        if index in string.digits:
            index = "#"
        elif index not in string.ascii_letters:
            index = "?"

        if index not in indexes:
            indexes[index] = []

        indexes[index].append((artist, name))

    return request.formatter(
        "artists",
        dict(
            ignoredArticles=ignored_articles_str(),
            index=[
                dict(
                    name=k,
                    artist=[
                        a.as_subsonic_artist(request.user)
                        for a, _ in sorted(v, key=lambda t: t[1].lower())
                    ],
                )
                for k, v in sorted(indexes.items())
            ],
        ),
    )


@api.route("/getArtist.view", methods=["GET", "POST"])
def artist_info():
    res = get_entity(Artist)
    info = res.as_subsonic_artist(request.user)
    albums = set(res.albums)
    albums |= {t.album for t in res.tracks}
    info["album"] = [
        a.as_subsonic_album(request.user)
        for a in sorted(albums, key=lambda a: a.sort_key())
    ]

    return request.formatter("artist", info)


@api.route("/getAlbum.view", methods=["GET", "POST"])
def album_info():
    res = get_entity(Album)
    info = res.as_subsonic_album(request.user)
    info["song"] = [
        t.as_subsonic_child(request.user, request.client)
        for t in sorted(res.tracks, key=lambda t: t.sort_key())
    ]

    return request.formatter("album", info)


@api.route("/getSong.view", methods=["GET", "POST"])
def track_info():
    res = get_entity(Track)
    return request.formatter(
        "song", res.as_subsonic_child(request.user, request.client)
    )
