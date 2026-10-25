"""Offline tests for the ESTOFEX list parser."""
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import estofex_warning_bot as bot  # noqa: E402

ARCHIVE_SNIPPET = """
<TR><TD ALIGN=CENTER><A HREF="/cgi-bin/polygon/showforecast.cgi?text=yes&fcstfile=2026102106_202610192036_2_stormforecast.xml"><P CLASS=small>Storm Forecast<BR>issued:Mon 19 Oct 2026 20:36</P></A></TD>
<TD ALIGN=CENTER><P CLASS=small><IMG SRC="/graphics/2.png"></P></TD></TR>
<TR><TD ALIGN=CENTER><A HREF="/cgi-bin/polygon/showforecast.cgi?text=yes&fcstfile=2026102003_202610191852_0_mesoscalediscussion.xml"><P CLASS=small>Mesoscale Discussion<BR>issued:Mon 19 Oct 2026 18:52</P></A></TD>
<TD ALIGN=CENTER><P CLASS=small><IMG SRC="/graphics/0.png"></P></TD></TR>
<TR><TD ALIGN=CENTER><A HREF="/cgi-bin/polygon/showforecast.cgi?text=yes&fcstfile=2026100706_202610051650_1_stormforecast.xml"><P CLASS=small>Storm Forecast<BR>issued:Mon 05 Oct 2026 16:50</P></A></TD>
<TD ALIGN=CENTER><P CLASS=small><IMG SRC="/graphics/1.png"></P></TD></TR>
"""

NO_FORECAST = "<TR><TD COLSPAN=5><P> No valid Storm Forecast available.</P></TD></TR>"


class FakeResponse:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        pass


def parse(page):
    with mock.patch.object(bot.requests, 'get', return_value=FakeResponse(page)):
        return bot.fetch_valid_forecasts()


def test_parses_rows_and_levels():
    rows = parse(ARCHIVE_SNIPPET)
    assert [r['level'] for r in rows] == [2, 0, 1]
    assert rows[0]['title'] == 'Storm Forecast'
    assert rows[0]['issued'] == 'Mon 19 Oct 2026 20:36'
    assert rows[0]['file'] == '2026102106_202610192036_2_stormforecast.xml'


def test_no_valid_forecast():
    assert parse(NO_FORECAST) == []


def test_build_text_contains_level_and_link():
    f = {'title': 'Storm Forecast', 'level': 2, 'issued': 'x', 'valid': 'y',
         'summary': 'A level 2 was issued.', 'url': 'https://example.org/f'}
    text = bot.build_text(f)
    assert 'LEVEL 2' in text and 'A level 2 was issued.' in text and 'https://example.org/f' in text
