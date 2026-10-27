"""A fact about a named future day must outlive 24 hours (#248).

The clock is frozen: Monday 26 Oct 2026, 12:00 in Asia/Kuala_Lumpur (UTC+8).
"""
import datetime as dt
import tempfile
import unittest
import zoneinfo
from pathlib import Path
from unittest import mock

from memory.expiry import dated_expiry, expiry_label, future_days
from memory.store import MemoryScope, MemoryStore

TZ_NAME = "Asia/Kuala_Lumpur"
TZ = zoneinfo.ZoneInfo(TZ_NAME)
DAY = 24 * 3600


def at(y, mo, d, h=0, mi=0):
    return dt.datetime(y, mo, d, h, mi, tzinfo=TZ).timestamp()


MONDAY_NOON = at(2026, 10, 26, 12)


def end_of(y, mo, d):
    """Last second of a local day: the item must be live then and gone one second later."""
    return at(y, mo, d) + DAY


class DatedExpiryRule(unittest.TestCase):
    def expiry(self, text, now=MONDAY_NOON):
        return dated_expiry(text, now, TZ_NAME)

    def test_same_day_errand_keeps_24_hours(self):
        for text in (
            "I'm dropping off groceries at 4 PM today.",
            "Sarah visits this afternoon",
            "Groceries arrive at 4 PM",
            "Sarah is calling tonight at 8 PM",
        ):
            self.assertIsNone(self.expiry(text), text)

    def test_weekday_later_this_week_lasts_to_end_of_that_day(self):
        got = self.expiry("Dad has a check-up with Dr. Tan on Thursday at 10 AM.")
        self.assertEqual(got, end_of(2026, 10, 29))
        self.assertEqual(self.expiry("Dr. Tan this Thursday at 10 AM"), end_of(2026, 10, 29))

    def test_next_weekday(self):
        self.assertEqual(self.expiry("Check-up next Tuesday at 10 AM"), end_of(2026, 11, 3))
        # the later reading of an ambiguous "next": next week's, never this week's
        self.assertEqual(self.expiry("Check-up next Thursday at 10 AM"), end_of(2026, 11, 5))
        self.assertEqual(
            dated_expiry("Check-up next Monday at 10 AM", at(2026, 10, 31, 9), TZ_NAME), end_of(2026, 11, 2)
        )

    def test_same_weekday_as_today_means_today_unless_next(self):
        self.assertIsNone(self.expiry("Sarah visits Monday at 4 PM"))
        self.assertEqual(self.expiry("Sarah visits next Monday at 4 PM"), end_of(2026, 11, 2))

    def test_tomorrow_and_day_after(self):
        self.assertEqual(self.expiry("Dentist tomorrow at 9 AM"), end_of(2026, 10, 27))
        self.assertEqual(self.expiry("Dentist the day after tomorrow at 9 AM"), end_of(2026, 10, 28))
        self.assertEqual(self.expiry("Dentist in 5 days at 9 AM"), end_of(2026, 10, 31))

    def test_explicit_dates(self):
        self.assertEqual(self.expiry("Eye test on 30 October at 2 PM"), end_of(2026, 10, 30))
        self.assertEqual(self.expiry("Eye test on Oct 30th at 2 PM"), end_of(2026, 10, 30))
        self.assertEqual(self.expiry("Eye test on 2026-11-04 at 2 PM"), end_of(2026, 11, 4))
        self.assertEqual(self.expiry("Eye test on the 30th at 2 PM"), end_of(2026, 10, 30))
        # a bare ordinal already gone this month is next month's
        self.assertEqual(self.expiry("Eye test on the 3rd at 2 PM"), end_of(2026, 11, 3))
        # a named month that is long gone is next year's; a recent one is a past event
        self.assertEqual(self.expiry("Check-up on March 3 at 10 AM"), end_of(2027, 3, 3))
        self.assertIsNone(self.expiry("Check-up was on Oct 20 at 10 AM"))
        self.assertIsNone(self.expiry("Doctor appointment was October 1 at 10 AM"))

    def test_explicit_year_is_taken_as_written(self):
        self.assertEqual(self.expiry("Eye test on 30 October 2027 at 2 PM"), end_of(2027, 10, 30))
        self.assertEqual(self.expiry("Eye test on October 30, 2027 at 2 PM"), end_of(2027, 10, 30))

    def test_year_after_a_comma_without_a_space(self):
        self.assertEqual(self.expiry("Check-up on October 30,2027 at 10 AM"), end_of(2027, 10, 30))

    def test_a_weekday_beside_a_past_date_is_not_a_future_event(self):
        self.assertIsNone(self.expiry("Check-up was Thursday 22 October 2026 at 10 AM"))

    def test_a_full_date_is_not_also_a_bare_ordinal(self):
        now = at(2026, 10, 30, 12)
        self.assertIsNone(dated_expiry("Eye test was on the 20th of October at 2 PM", now, TZ_NAME))

    def test_week_wording_is_generous(self):
        self.assertEqual(self.expiry("Physio this week at 3 PM"), end_of(2026, 11, 1))
        self.assertEqual(self.expiry("Physio next week at 3 PM"), end_of(2026, 11, 8))

    def test_recurring_and_past_wording_name_no_day(self):
        for text in (
            "Bridge club every Thursday at 2 PM",
            "Bridge club on Thursdays at 2 PM",
            "He saw Dr. Tan last Thursday at 10 AM",
            "Yesterday's walk was at 9 AM",
        ):
            self.assertIsNone(self.expiry(text), text)

    def test_latest_named_day_wins(self):
        self.assertEqual(self.expiry("Sarah visits tomorrow and Friday at 3 PM"), end_of(2026, 10, 30))

    def test_never_shorter_than_24_hours(self):
        # Sunday 23:00 "this week" would end in an hour; the old 24 h life stays.
        self.assertIsNone(dated_expiry("Physio this week at 3 PM", at(2026, 11, 1, 23), TZ_NAME))

    def test_today_is_the_household_day_not_utc(self):
        # 23:30 UTC Monday is already Tuesday in Kuala Lumpur: "Wednesday" is tomorrow there.
        now = dt.datetime(2026, 10, 26, 23, 30, tzinfo=dt.timezone.utc).timestamp()
        self.assertEqual(dated_expiry("Dr. Tan on Wednesday at 10 AM", now, TZ_NAME), end_of(2026, 10, 28))
        self.assertEqual(
            dated_expiry("Dr. Tan on Wednesday at 10 AM", now, "UTC"), at(2026, 10, 29) + 8 * 3600
        )

    def test_future_days_ignores_nothing_dated(self):
        self.assertEqual(future_days("Dad loves jazz", dt.date(2026, 10, 26)), [])


class DrTanMemoStaysUntilThursday(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data_dir = Path(self.tmp.name)

    def store(self):
        return MemoryStore("p", self.data_dir, timezone_str=TZ_NAME)

    def test_memo_is_recalled_on_wednesday_and_gone_after_thursday(self):
        memo = "Dad has a check-up with Dr. Tan on Thursday at 10 AM."
        with mock.patch("memory.store.time.time", return_value=MONDAY_NOON):
            item = self.store().add(memo, source="caregiver_memo")
        self.assertEqual(item.scope, MemoryScope.TEMPORARY.value)
        self.assertEqual(item.expires_at, end_of(2026, 10, 29))

        store = self.store()
        wednesday = at(2026, 10, 28, 9)
        self.assertIn(memo, store.caregiver_schedule_updates(now=wednesday))
        self.assertIn(memo, store.caregiver_schedule_updates(now=at(2026, 10, 29, 23, 59)))
        self.assertNotIn(memo, store.caregiver_schedule_updates(now=at(2026, 10, 30)))

    def test_same_day_errand_still_expires_in_24_hours(self):
        memo = "I'm dropping off groceries at 4 PM today"
        with mock.patch("memory.store.time.time", return_value=MONDAY_NOON):
            item = self.store().add(memo, source="caregiver_memo")
        self.assertEqual(item.expires_at, MONDAY_NOON + DAY)
        self.assertNotIn(memo, self.store().caregiver_schedule_updates(now=MONDAY_NOON + DAY + 1))

    def test_an_explicit_expiry_is_never_overridden(self):
        with mock.patch("memory.store.time.time", return_value=MONDAY_NOON):
            item = self.store().add(
                "Dr. Tan on Thursday at 10 AM", source="caregiver_memo",
                scope=MemoryScope.TEMPORARY.value, expires_at=MONDAY_NOON + 600,
            )
        self.assertEqual(item.expires_at, MONDAY_NOON + 600)

    def test_permanent_facts_stay_permanent(self):
        with mock.patch("memory.store.time.time", return_value=MONDAY_NOON):
            item = self.store().add("Bridge club is every Thursday", source="caregiver_memo")
        self.assertEqual(item.scope, MemoryScope.PERMANENT.value)
        self.assertIsNone(item.expires_at)


class ExpiryLabel(unittest.TestCase):
    def test_label_names_the_day_and_time(self):
        self.assertEqual(expiry_label(end_of(2026, 10, 29), MONDAY_NOON, TZ_NAME), "Thu 23:59")
        self.assertEqual(expiry_label(end_of(2026, 11, 3), MONDAY_NOON, TZ_NAME), "Tue 3 Nov 23:59")

    def test_short_expiry_keeps_the_countdown(self):
        self.assertEqual(expiry_label(MONDAY_NOON + 5 * 3600 - 60, MONDAY_NOON, TZ_NAME), "in 4h 59m")
        self.assertEqual(expiry_label(MONDAY_NOON + DAY, MONDAY_NOON, TZ_NAME), "in 24h 0m")


class PanelLabel(unittest.TestCase):
    def test_caregiver_panel_says_when_the_memo_expires(self):
        import webapp

        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(webapp, "SENIOR_TIMEZONE", TZ_NAME), \
                mock.patch.object(webapp, "_session_dirs", return_value=(Path(tmp), Path(tmp))):
            store = MemoryStore(webapp.DEFAULT_PROFILE_ID, Path(tmp), timezone_str=TZ_NAME)
            with mock.patch("memory.store.time.time", return_value=MONDAY_NOON):
                store.add("Dad has a check-up with Dr. Tan on Thursday at 10 AM.", source="caregiver_memo")
            with mock.patch("webapp.time.time", return_value=MONDAY_NOON):
                panel = webapp._format_caregiver_panel("anysession")
        self.assertIn("[Temporary — expires Thu 23:59]", panel)
        self.assertNotIn("23h 59m", panel)


if __name__ == "__main__":
    unittest.main()
