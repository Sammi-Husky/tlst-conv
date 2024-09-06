# MIT License
#
# Copyright (c) 2024 Sammi Husky
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from __future__ import annotations

import json
import os
import struct
import io

from argparse import ArgumentParser
from pathlib import Path


class TLSTJsonEncoder(json.JSONEncoder):
    """Custom JSON encoder for TLSTEntry and TLST objects"""

    def default(self, o):
        if isinstance(o, TLSTEntry):
            return {
                "songId": o.songId,
                "delay": o.delay,
                "volume": o.volume,
                "frequency": o.frequency,
                "switch": o.switch,
                "disablePinch": o.disablePinch,
                "disableTlstInclusion": o.disableTlstInclusion,
                "title": o.title,
                "filename": o.filename,
            }
        elif isinstance(o, TLST):
            return {
                "tracks": o.tracks,
            }
        else:
            return super().default(o)


class TLSTJsonDecoder(json.JSONDecoder):
    """Custom JSON decoder for TLSTEntry and TLST objects"""

    def __init__(self, *args, **kwargs):
        super().__init__(object_hook=self.dict_to_object, *args, **kwargs)

    def dict_to_object(self, d):
        if "songId" in d:
            entry = TLSTEntry()
            entry.songId = d["songId"]
            entry.delay = d["delay"]
            entry.volume = d["volume"]
            entry.frequency = d["frequency"]
            entry.switch = d["switch"]
            entry.disablePinch = d["disablePinch"]
            entry.disableTlstInclusion = d["disableTlstInclusion"]
            entry.title = d["title"]
            entry.filename = d["filename"]
            return entry
        elif "tracks" in d:
            tlst = TLST()
            tlst.tracks = d["tracks"]
            return tlst
        return d


def readNTString(f: io.BufferedReader) -> str:
    """Reads a null terminated string from a binary file"""
    data = b""
    while (c := f.read(1)) != b"\x00":
        data += c
    s = data.decode("utf-8")
    return s


class TLSTEntry:
    """Represents a single track entry in a TLST file"""

    def __init__(self) -> None:
        self.songId = 0
        self.delay = 0
        self.volume = 0
        self.frequency = 0
        self.switch = 0
        self.disablePinch = False
        self.disableTlstInclusion = False
        self.title = ""
        self.filename = ""

    songId: int
    delay: int
    volume: int
    frequency: int
    switch: int
    disablePinch: bool
    disableTlstInclusion: bool
    title: str
    filename: str


class TLST:
    """Represents a TLST file"""

    def __init__(self) -> None:
        self.tracks = []

    @staticmethod
    def fromJson(path: str) -> TLST:
        with open(path, "r") as f:
            return json.load(f, cls=TLSTJsonDecoder)

    def toJson(self, path: str) -> None:
        with open(path, "w") as f:
            json.dump(self, fp=f, indent=4, cls=TLSTJsonEncoder)

    def getJson(self) -> str:
        return json.dumps(self, indent=4, cls=TLSTJsonEncoder)

    @staticmethod
    def fromTlst(path: str) -> TLST:
        with open(path, "rb") as f:
            tlst = TLST()
            entries = []

            # skip magic
            f.seek(0x4, io.SEEK_SET)

            # read number of entries
            numEntries = struct.unpack(">I", f.read(4))[0]

            # skip size
            f.seek(0x2, io.SEEK_CUR)

            # read string offset
            stringsOffset = struct.unpack(">H", f.read(2))[0]

            # get data for each entry
            for x in range(numEntries):
                f.seek(x * 0x10 + 0xC, io.SEEK_SET)
                entry = TLSTEntry()
                entry.songId = struct.unpack(">I", f.read(4))[0]
                entry.delay = struct.unpack(">H", f.read(2))[0]
                entry.volume = struct.unpack(">b", f.read(1))[0]
                entry.frequency = struct.unpack(">b", f.read(1))[0]

                # we don't store the offsets, but we use them to get the actual strings
                filenameOffset = struct.unpack(">H", f.read(2))[0]
                titleOffset = struct.unpack(">H", f.read(2))[0]

                entry.switch = struct.unpack(">H", f.read(2))[0]
                entry.disablePinch = struct.unpack(">?", f.read(1))[0]
                entry.disableTlstInclusion = struct.unpack(">?", f.read(1))[0]

                # title and filename are optional, only read if the offset is not 0xFFFF
                if titleOffset != 0xFFFF:
                    f.seek(titleOffset + stringsOffset, io.SEEK_SET)
                    entry.title = readNTString(f)

                if filenameOffset != 0xFFFF:
                    f.seek(filenameOffset + stringsOffset, io.SEEK_SET)
                    entry.filename = readNTString(f)

                entries.append(entry)
                if f.tell() == f.seek(0, io.SEEK_END):
                    break

            tlst.tracks = entries
            return tlst

    def toTlst(self, path: str) -> None:
        with open(path, "wb") as f:
            f.write(b"TLST")  # magic
            f.write(struct.pack(">I", len(self.tracks)))  # number of entries

            # skip size and string offset for now, we'll fill it in later
            f.seek(0xC, io.SEEK_SET)

            # write the actual data for each entry, using placeholders for title and filename offsets
            for entry in self.tracks:
                f.write(struct.pack(">I", entry.songId))
                f.write(struct.pack(">H", entry.delay))
                f.write(struct.pack(">b", entry.volume))
                f.write(struct.pack(">b", entry.frequency))

                # placeholders, will get overwritten later
                f.write(struct.pack(">H", 0xFFFF))
                f.write(struct.pack(">H", 0xFFFF))

                f.write(struct.pack(">H", entry.switch))
                f.write(struct.pack(">?", entry.disablePinch))
                f.write(struct.pack(">?", entry.disableTlstInclusion))

            # store offset to string table
            stringsOffset = f.tell()

            for x in range(0, len(self.tracks)):
                entry = self.tracks[x]

                # if the filename is empty, we don't write it and the offset stays 0xFFFF
                filenameOff = f.tell()
                if entry.filename != "":
                    f.write(entry.filename.encode("utf-8"))
                    f.write(b"\x00")

                    # save our current position so we can go back to it
                    prevOff = f.tell()
                    f.seek(x * 0x10 + 0xC + 0x8, io.SEEK_SET)

                    # overwrite the placeholder with the actual offset
                    f.write(struct.pack(">H", filenameOff - stringsOffset))

                    # go back to where we were before writing the filename
                    f.seek(prevOff, io.SEEK_SET)

                # if the title is empty, we don't write it and the offset stays 0xFFFF
                titleOff = f.tell()
                if entry.title != "":
                    f.write(entry.title.encode("utf-8"))
                    f.write(b"\x00")

                    # save our current position so we can go back to it
                    prevOff = f.tell()
                    f.seek(x * 0x10 + 0xC + 0xA, io.SEEK_SET)

                    # overwrite the placeholder with the actual offset
                    f.write(struct.pack(">H", titleOff - stringsOffset))

                    # go back to where we were before writing the title
                    f.seek(prevOff, io.SEEK_SET)

            totalSize = f.tell()  # get the total size of the file
            f.seek(0x8, io.SEEK_SET)  # seek back to the skipped header fields
            f.write(struct.pack(">H", totalSize))  # write the total size
            f.write(struct.pack(">H", stringsOffset))  # write the string offset


class TLSTProcessor:
    """Helper class to convert TLST files to and from json or binary format"""

    def __init__(self, dirMode=False) -> None:
        self.isDirMode = dirMode

    def processJson(self, inputPath: str, outPath: str | None):
        if outPath is None:
            outPath = inputPath.replace(".json", ".tlst")

        if os.path.isdir(outPath):
            filename = Path(inputPath).name.replace(".json", ".tlst")
            outPath = os.path.join(outPath, filename)

        tlst = TLST.fromJson(inputPath)
        tlst.toTlst(outPath)

    def processTlst(self, inputPath: str, outPath: str | None):
        if outPath is None:
            outPath = inputPath.replace(".tlst", ".json")

        if os.path.isdir(outPath):
            filename = Path(inputPath).name.replace(".tlst", ".json")
            outPath = os.path.join(outPath, filename)

        tlst = TLST.fromTlst(inputPath)
        tlst.toJson(outPath)

    def processFile(self, inputPath: str, outPath: str | None) -> bool:
        errStatus = False
        if inputPath.endswith(".json"):
            self.processJson(inputPath, outPath)
            errStatus = False
        elif inputPath.endswith(".tlst"):
            self.processTlst(inputPath, outPath)
            errStatus = False
        else:
            errStatus = True
        return errStatus


def gatherFiles(path: str, extension: str) -> list[str]:
    """Recursively gather all files with a specific extension in a directory"""
    paths = []
    for root, _, files in os.walk(path):
        for file in files:
            if file.endswith(extension):
                paths.append(os.path.join(root, file))
    return paths


def main():
    parser = ArgumentParser(usage="%(prog)s [options] input")
    parser.add_argument("input", help="input file", nargs="+", default=[])
    parser.add_argument(
        "-x",
        "--extract",
        help="extract tlst to json",
        action="store_true",
        dest="extract",
        default=False,
    )
    parser.add_argument(
        "-o",
        "--output",
        help="output file",
        default=None,
        dest="output",
    )
    args = parser.parse_args()
    outPath = args.output
    mode = "extract" if args.extract else "build"

    paths = []
    isDirMode = False
    if len(args.input) == 1 and os.path.isdir(args.input[0]):
        isDirMode = True
        if mode == "extract":
            paths = gatherFiles(args.input[0], ".tlst")
        elif mode == "build":
            paths = gatherFiles(args.input[0], ".json")
    else:
        paths = args.input

    if isDirMode and outPath is not None:
        os.makedirs(outPath, exist_ok=True)

    for inputPath in paths:
        print(inputPath)
        processor = TLSTProcessor(isDirMode)
        processor.processFile(inputPath, outPath)


if __name__ == "__main__":
    main()
